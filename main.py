"""Travel Planning Agent Implementation."""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import aiohttp
from openai import OpenAI
import json
import ssl
import certifi
from dataclasses import dataclass
from enum import Enum


@dataclass
class TravelPreferences:
    budget: float
    style: str  # luxury, budget, mid-range
    interests: List[str]
    dietary_restrictions: List[str]
    accessibility_needs: List[str]


class BookingStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Booking:
    id: str
    type: str
    status: BookingStatus
    details: Dict
    confirmation: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'type': self.type,
            'status': self.status.value,
            'details': self.details,
            'confirmation': self.confirmation
        }


class MockFoursquareClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(connector=connector)

    async def search_venues(self, ll: str, radius: int, categories: List[str]) -> Dict:
        """Search for venues near the given coordinates."""
        await asyncio.sleep(1)  # Simulated API delay
        venues = [
            {
                "id": "v123",
                "name": "Eiffel Tower",
                "categories": [{"name": "Monument"}],
                "location": {
                    "lat": 48.8584,
                    "lng": 2.2945,
                    "address": "Champ de Mars"
                }
            },
            {
                "id": "v124",
                "name": "Louvre Museum",
                "categories": [{"name": "Museum"}],
                "location": {
                    "lat": 48.8606,
                    "lng": 2.3376,
                    "address": "Rue de Rivoli"
                }
            }
        ]
        return {"response": {"venues": venues}}

    async def get_venue_details(self, venue_id: str) -> Dict:
        """Get detailed information about a venue."""
        await asyncio.sleep(1)  # Simulated API delay
        return {
            "response": {
                "venue": {
                    "rating": 4.8,
                    "price": {"tier": 2},
                    "hours": {"status": "Open until 11:00 PM"},
                    "description": "Famous landmark and museum",
                    "url": "https://example.com",
                    "photos": {"groups": []}
                }
            }
        }

    async def close(self):
        await self.session.close()


class TravelPlanningAgent:
    def __init__(self, openai_api_key: str, amadeus_api_key: str, amadeus_api_secret: str, foursquare_api_key: str):
        self.client = OpenAI(api_key=openai_api_key)
        self.amadeus_api_key = amadeus_api_key
        self.amadeus_api_secret = amadeus_api_secret
        self.foursquare = MockFoursquareClient(api_key=foursquare_api_key)
        self.amadeus_token = None

        # SSL context for macOS
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(connector=connector)

        self.current_plan = {
            "flights": [],
            "hotels": [],
            "activities": []
        }
        self.preferences = None

    async def close(self):
        """Close all client sessions."""
        await self.foursquare.close()
        await self.session.close()

    async def plan_trip(self, origin: str, destination: str, start_date: datetime, end_date: datetime,
                        preferences: TravelPreferences) -> Dict:
        """Plan a complete trip including flights, hotels, and activities."""
        try:
            self.preferences = {
                'origin_city': origin,
                'destination_city': destination,
                'start_date': start_date,
                'end_date': end_date,
                'style': preferences.style,
                'budget': preferences.budget,
                'interests': preferences.interests,
                'dietary_restrictions': preferences.dietary_restrictions,
                'accessibility_needs': preferences.accessibility_needs,
                'guests': 2
            }

            # Search and book flights
            flights = await self._search_flights()
            if flights:
                flight_booking = await self._book_flight(flights[0])
                self.current_plan['flights'].append(flight_booking)

            # Search and book hotels
            hotels = await self._search_hotels()
            if hotels:
                hotel_booking = await self._book_hotel(hotels[0])
                self.current_plan['hotels'].append(hotel_booking)

            # Search and book activities
            activities = await self._search_activities()
            for activity in activities[:3]:
                activity_booking = await self._book_activity(activity)
                self.current_plan['activities'].append(activity_booking)

            return self.current_plan

        except Exception as e:
            raise Exception(f"Trip planning failed: {str(e)}")

    async def _get_amadeus_token(self) -> str:
        """Get Amadeus API access token."""
        try:
            url = "https://test.api.amadeus.com/v1/security/oauth2/token"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = {
                "grant_type": "client_credentials",
                "client_id": self.amadeus_api_key,
                "client_secret": self.amadeus_api_secret
            }

            async with self.session.post(url, headers=headers, data=data) as response:
                if response.status == 200:
                    token_data = await response.json()
                    self.amadeus_token = token_data["access_token"]
                    print("Successfully obtained Amadeus token")
                    return self.amadeus_token
                else:
                    error_text = await response.text()
                    print(f"Failed to get token. Status: {response.status}, Response: {error_text}")
                    raise Exception(f"Failed to get Amadeus token: {error_text}")

        except Exception as e:
            print(f"Error getting Amadeus token: {str(e)}")
            raise

    def _map_interests_to_categories(self) -> List[str]:
        """Map user interests to Foursquare category IDs."""
        interest_mapping = {
            "history": ["4deefb944765f83613cdba6e"],  # Historic Site
            "food": ["4d4b7105d754a06374d81259"],  # Food
            "nature": ["4d4b7105d754a06377d81259"],  # Outdoors
            "culture": ["4d4b7104d754a06370d81259"],  # Arts & Entertainment
            "shopping": ["4d4b7105d754a06378d81259"]  # Shop & Service
        }

        categories = []
        for interest in self.preferences.get('interests', []):
            if interest in interest_mapping:
                categories.extend(interest_mapping[interest])
        return categories

    async def _search_flights(self) -> List[Dict]:
        """Search for flights using Amadeus API."""
        try:
            print("Starting flight search...")
            date = self.preferences.get('start_date')
            origin_code = "JFK"  # New York
            dest_code = "CDG"  # Paris

            token = await self._get_amadeus_token()
            print(f"Searching flights from {origin_code} to {dest_code} for {date.strftime('%Y-%m-%d')}")

            url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
            headers = {
                "Authorization": f"Bearer {token}"
            }
            params = {
                "originLocationCode": origin_code,
                "destinationLocationCode": dest_code,
                "departureDate": date.strftime("%Y-%m-%d"),
                "adults": "1",
                "max": "5"
            }

            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'data' in data:
                        print(f"Found {len(data['data'])} flight offers")
                        return [
                            {
                                'id': offer['id'],
                                'price': float(offer['price']['total']),
                                'airline': offer['itineraries'][0]['segments'][0]['carrierCode'],
                                'departure_time': offer['itineraries'][0]['segments'][0]['departure']['at'],
                                'arrival_time': offer['itineraries'][0]['segments'][-1]['arrival']['at'],
                                'stops': len(offer['itineraries'][0]['segments']) - 1
                            }
                            for offer in data['data']
                        ]
                    else:
                        print("No flight offers found in response")
                        return []
                else:
                    error_text = await response.text()
                    raise Exception(f"Flight search failed: {error_text}")

        except Exception as e:
            print(f"Error in flight search: {str(e)}")
            raise

    async def _search_hotels(self) -> List[Dict]:
        """Search for hotels using Amadeus API."""
        try:
            print("Starting hotel search...")
            destination = self.preferences.get('destination_city')

            # Get fresh token for hotel search
            token = await self._get_amadeus_token()

            print(f"Converting {destination} to IATA code...")
            location_url = "https://test.api.amadeus.com/v1/reference-data/locations"
            headers = {
                "Authorization": f"Bearer {token}"
            }
            location_params = {
                "keyword": destination,
                "subType": "CITY",
                "page[limit]": "1"
            }

            async with self.session.get(location_url, headers=headers, params=location_params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Location search failed: {error_text}")

                location_data = await response.json()
                if not location_data.get('data'):
                    raise Exception(f"No IATA code found for destination city: {destination}")

                location_info = location_data['data'][0]
                iata_code = location_info['iataCode']
                latitude = location_info.get('geoCode', {}).get('latitude')
                longitude = location_info.get('geoCode', {}).get('longitude')
                print(f"Found location info: {iata_code} ({latitude}, {longitude})")

            # Step 1: Find hotels in the area using geocode
            print(f"Searching hotels in {destination}...")
            hotels_url = "https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-geocode"
            hotels_params = {
                "latitude": latitude,
                "longitude": longitude,
                "radius": 20,
                "radiusUnit": "KM",
                "hotelSource": "ALL"
            }

            print(f"Looking up hotels by geocode with params: {hotels_params}")
            async with self.session.get(hotels_url, headers=headers, params=hotels_params) as response:
                response_text = await response.text()
                print(f"Response status: {response.status}")

                if response.status != 200:
                    raise Exception(f"Hotel geocode search failed: {response_text}")

                hotels_list = json.loads(response_text)
                if not hotels_list.get('data'):
                    print("No hotels found in area")
                    return []

                print(f"Found {len(hotels_list['data'])} hotels in area")

                # Step 2: Get offers for each hotel
                # Step 2: Get offers for each hotel
                hotels = []
                for hotel_data in hotels_list['data'][:5]:  # Limit to 5 hotels
                    try:
                        hotel_id = hotel_data['hotelId']

                        # Get offers for this specific hotel
                        offers_url = "https://test.api.amadeus.com/v3/shopping/hotel-offers"
                        offers_params = {
                            "hotelIds": hotel_id,
                            "adults": str(self.preferences.get('guests', 1)),
                            "checkInDate": self.preferences.get('start_date').strftime("%Y-%m-%d"),
                            "checkOutDate": self.preferences.get('end_date').strftime("%Y-%m-%d"),
                            "currency": "EUR",
                            "bestRateOnly": "true"
                        }

                        print(f"\nTrying to get offers for hotel {hotel_id}")
                        print(f"Offers request params: {offers_params}")

                        async with self.session.get(offers_url, headers=headers,
                                                    params=offers_params) as offers_response:
                            offers_text = await offers_response.text()
                            print(f"Offers response status: {offers_response.status}")
                            print(f"Offers response: {offers_text}")

                            if offers_response.status == 200:
                                offers_data = json.loads(offers_text)
                                if offers_data.get('data'):
                                    offer = offers_data['data'][0]
                                    hotel = {
                                        'id': hotel_id,
                                        'name': hotel_data.get('name', 'Unknown Hotel'),
                                        'price': float(offer['offers'][0]['price']['total']),
                                        'rating': float(hotel_data.get('rating', '3.0')),  # Default to 3.0 rating
                                        'location': {
                                            'latitude': float(hotel_data.get('latitude', '0')),
                                            'longitude': float(hotel_data.get('longitude', '0')),
                                            'address': hotel_data.get('address', {}).get('lines', ['No address'])[0]
                                        }
                                    }

                                    if self._matches_hotel_preferences(hotel):
                                        print(f"Adding hotel: {hotel['name']} to results")
                                        hotels.append(hotel)
                                    else:
                                        print(f"Hotel {hotel['name']} didn't match preferences")
                            else:
                                print(f"Failed to get offers for hotel {hotel_id}: {offers_text}")
                    except Exception as e:
                        print(f"Error processing hotel {hotel_id}: {str(e)}")
                        continue

                print(f"Successfully processed {len(hotels)} hotels with offers")
                return hotels

        except Exception as e:
            print(f"Error in hotel search: {str(e)}")
            raise Exception(f"Hotel search failed: {str(e)}")

    async def _search_activities(self) -> List[Dict]:
        """Search for activities using Foursquare API."""
        try:
            print("Starting activity search...")

            if self.current_plan['hotels'] and len(self.current_plan['hotels']) > 0:
                hotel = self.current_plan['hotels'][0]
                lat = hotel.details['location']['latitude']
                lng = hotel.details['location']['longitude']
                # This code continues from where we left off in the _search_activities method
                # Add this after `lng = hotel.details['location']['longitude']`

                print(f"Using hotel coordinates: {lat}, {lng}")
            else:
                # Default coordinates for Paris city center
                lat = 48.85334
                lng = 2.34889
                print(f"Using city center coordinates: {lat}, {lng}")

            print("Searching for venues...")
            venues = await self.foursquare.search_venues(
                ll=f"{lat},{lng}",
                radius=5000,  # 5km radius
                categories=self._map_interests_to_categories()
            )

            if not venues.get('response', {}).get('venues'):
                print("No venues found")
                return []

            activities = []
            print(f"Found {len(venues['response']['venues'])} venues")

            for venue in venues['response']['venues']:
                try:
                    print(f"Getting details for venue: {venue['name']}")
                    details = await self.foursquare.get_venue_details(venue['id'])
                    venue_details = details['response']['venue']

                    activity = {
                        'id': venue['id'],
                        'name': venue['name'],
                        'category': venue['categories'][0]['name'] if venue['categories'] else 'Unknown',
                        'rating': venue_details.get('rating', 0),
                        'price_tier': venue_details.get('price', {}).get('tier', 0),
                        'location': {
                            'latitude': venue['location']['lat'],
                            'longitude': venue['location']['lng'],
                            'address': venue['location'].get('address', ''),
                        },
                        'hours': venue_details.get('hours', {}).get('status', 'Hours not available'),
                        'description': venue_details.get('description', ''),
                        'url': venue_details.get('url', '')
                    }

                    if self._matches_activity_preferences(activity):
                        activities.append(activity)

                except Exception as e:
                    print(f"Error processing venue {venue.get('name', 'unknown')}: {str(e)}")
                    continue

            print(f"Successfully processed {len(activities)} activities")
            return activities

        except Exception as e:
            print(f"Error in activity search: {str(e)}")
            raise

    def _matches_hotel_preferences(self, hotel: Dict) -> bool:
        """Check if a hotel matches user preferences."""
        try:
            if self.preferences.get('style'):
                price = hotel.get('price', 0)
                # More lenient price ranges
                if self.preferences['style'] == 'luxury' and price < 200:
                    return False
                elif self.preferences['style'] == 'budget' and price > 300:
                    return False
                elif self.preferences['style'] == 'mid-range' and (price < 100 or price > 500):
                    return False

            print(f"Hotel {hotel.get('name')} matches preferences")
            return True
        except Exception as e:
            print(f"Error checking hotel preferences: {str(e)}")
            return True  # Be more lenient in case of errors

    def _matches_activity_preferences(self, activity: Dict) -> bool:
        """Check if an activity matches user preferences."""
        try:
            # Make category matching more lenient
            if self.preferences.get('interests'):
                # Consider the activity name as well as category
                text_to_match = f"{activity['name']} {activity.get('category', '')}".lower()
                category_matches = any(
                    interest.lower() in text_to_match
                    for interest in self.preferences['interests']
                )

                # Add some default categories that always match
                default_matches = any(
                    keyword in text_to_match
                    for keyword in ['museum', 'monument', 'tower', 'palace', 'park', 'garden']
                )

                if not (category_matches or default_matches):
                    return False

            # More lenient price tier matching
            if self.preferences.get('style'):
                price_tier = activity.get('price_tier', 1)  # Default to affordable
                if self.preferences['style'] == 'luxury' and price_tier < 1:
                    return False
                elif self.preferences['style'] == 'budget' and price_tier > 3:
                    return False

            print(f"Activity {activity.get('name')} matches preferences")
            return True
        except Exception as e:
            print(f"Error checking activity preferences: {str(e)}")
            return True  # Be more lenient in case of errors

    async def _book_flight(self, flight: Dict) -> Optional[Booking]:
        """Book a flight."""
        try:
            # Mock implementation
            await asyncio.sleep(1)
            return Booking(
                id=f"FLIGHT-{flight['id']}",
                type="flight",
                status=BookingStatus.CONFIRMED,
                details=flight,
                confirmation=f"CONF-{flight['id']}"
            )
        except Exception as e:
            raise Exception(f"Flight booking failed: {str(e)}")

    async def _book_hotel(self, hotel: Dict) -> Optional[Booking]:
        """Book a hotel."""
        try:
            # Mock implementation
            await asyncio.sleep(1)
            return Booking(
                id=f"HOTEL-{hotel['id']}",
                type="hotel",
                status=BookingStatus.CONFIRMED,
                details=hotel,
                confirmation=f"CONF-{hotel['id']}"
            )
        except Exception as e:
            raise Exception(f"Hotel booking failed: {str(e)}")

    async def _book_activity(self, activity: Dict) -> Optional[Booking]:
        """Book an activity."""
        try:
            # Mock implementation
            await asyncio.sleep(1)
            return Booking(
                id=f"ACT-{activity['id']}",
                type="activity",
                status=BookingStatus.CONFIRMED,
                details=activity,
                confirmation=f"CONF-{activity['id']}"
            )
        except Exception as e:
            raise Exception(f"Activity booking failed: {str(e)}")

async def main():
    agent = None
    try:
        agent = TravelPlanningAgent(
            openai_api_key='your-openai-api-key',
            amadeus_api_key="yourkey",
            amadeus_api_secret="yourkey",
            foursquare_api_key="your-foursquare-api-key"
        )

        preferences = TravelPreferences(
            budget=5000.0,
            style="mid-range",
            interests=["history", "food", "nature"],
            dietary_restrictions=["vegetarian"],
            accessibility_needs=[]
        )

        itinerary = await agent.plan_trip(
            origin="New York",
            destination="Paris",
            start_date=datetime.now() + timedelta(days=30),
            end_date=datetime.now() + timedelta(days=37),
            preferences=preferences
        )

        # Convert bookings to dictionaries for JSON serialization
        serializable_itinerary = {
            "flights": [booking.to_dict() for booking in itinerary["flights"]],
            "hotels": [booking.to_dict() for booking in itinerary["hotels"]],
            "activities": [booking.to_dict() for booking in itinerary["activities"]]
        }

        print("Trip planning successful!")
        print(json.dumps(serializable_itinerary, indent=2))

    except Exception as e:
        print(f"Trip planning failed: {str(e)}")
    finally:
        if agent:
            await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
