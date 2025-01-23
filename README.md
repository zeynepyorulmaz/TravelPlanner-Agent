# Travel Planning Agent

An asynchronous Python-based travel planning system that integrates with Amadeus, Foursquare, and OpenAI APIs to create personalized travel itineraries.

## Features

- Flight search and booking via Amadeus API
- Hotel recommendations based on location and preferences
- Activity suggestions using Foursquare API
- Customizable travel preferences (budget, style, interests)
- Support for dietary restrictions and accessibility needs
- Asynchronous operations for improved performance

## Prerequisites

- Python 3.7+
- aiohttp
- openai
- certifi
- AsyncIO support

## API Keys Required

- Amadeus API (key and secret)
- Foursquare API key
- OpenAI API key

## Installation

```bash
pip install aiohttp openai certifi
```

## Usage

```python
from datetime import datetime, timedelta
from travel_planning_agent import TravelPlanningAgent, TravelPreferences

async def plan_trip():
    agent = TravelPlanningAgent(
        openai_api_key='your-openai-key',
        amadeus_api_key='your-amadeus-key',
        amadeus_api_secret='your-amadeus-secret',
        foursquare_api_key='your-foursquare-key'
    )

    preferences = TravelPreferences(
        budget=5000.0,
        style="mid-range",
        interests=["history", "food", "nature"],
        dietary_restrictions=["vegetarian"],
        accessibility_needs=[]
    )

    try:
        itinerary = await agent.plan_trip(
            origin="New York",
            destination="Paris",
            start_date=datetime.now() + timedelta(days=30),
            end_date=datetime.now() + timedelta(days=37),
            preferences=preferences
        )
        print(itinerary)
    finally:
        await agent.close()
```


## Data Classes

### TravelPreferences
```python
@dataclass
class TravelPreferences:
    budget: float
    style: str  # luxury, budget, mid-range
    interests: List[str]
    dietary_restrictions: List[str]
    accessibility_needs: List[str]
```

### Booking
```python
@dataclass
class Booking:
    id: str
    type: str
    status: BookingStatus
    details: Dict
    confirmation: Optional[str]
```

