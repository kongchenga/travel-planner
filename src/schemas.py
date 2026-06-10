"""Structured Pydantic schemas for the trip plan.

Each agent outputs its corresponding model.
RoutePlan = one self-contained route (balanced to budget).
TripPlan = multiple RoutePlans + shared destination info.
"""

from pydantic import BaseModel, Field
from typing import Optional


class Activity(BaseModel):
    time_slot: str = ""      # "09:00-12:00" or "上午/下午/晚上"
    description: str = ""    # e.g. "参观故宫博物院"
    location: str = ""       # POI name (must be real)
    poi_location: str = ""   # "lng,lat" from real POI
    duration_min: int = 0
    cost: float = 0
    transport: str = ""      # "步行/驾车/地铁"


class DayPlan(BaseModel):
    day_number: int = 0
    date: str = ""
    title: str = ""
    activities: list[Activity] = []


class FlightOption(BaseModel):
    airline: str = ""
    route: str = ""           # "上海→北京"
    price_estimate: float = 0
    duration_min: int = 0
    recommendation: str = ""


class HotelOption(BaseModel):
    name: str = ""
    address: str = ""
    price_per_night: float = 0
    rating: float = 0
    tier: str = "comfort"     # "economy" / "comfort" / "luxury"
    phone: str = ""
    location: str = ""        # "lng,lat"


class DiningOption(BaseModel):
    name: str = ""
    address: str = ""
    cuisine: str = ""
    price_per_person: float = 0
    rating: float = 0
    phone: str = ""
    location: str = ""


class BudgetItem(BaseModel):
    category: str = ""        # "交通" / "住宿" / "餐饮" ...
    amount: float = 0
    percentage: float = 0     # 0-100


class DestinationInfo(BaseModel):
    summary: str = ""
    best_season: str = ""
    attractions: list[str] = []
    weather: str = ""
    tips: str = ""


class RoutePlan(BaseModel):
    """One self-contained route option, fully budget-balanced."""
    name: str = ""              # Route label, e.g. "经典打卡路线" / "深度文化路线"
    description: str = ""       # One-line summary of what this route is about
    total_cost: float = 0       # Sum of all costs in this route
    flights: list[FlightOption] = []
    hotels: list[HotelOption] = []
    dining: list[DiningOption] = []
    budget: list[BudgetItem] = []
    days: list[DayPlan] = []
    map_data: dict = {}         # Per-route map markers/routes


class TripPlan(BaseModel):
    destination: str = ""
    origin: str = ""
    travelers: int = 1
    total_budget: float = 0
    currency: str = "CNY"
    start_date: str = ""
    end_date: str = ""

    destination_info: DestinationInfo = Field(default_factory=DestinationInfo)
    routes: list[RoutePlan] = []   # Multiple route options
