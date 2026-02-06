"""
Dataset Registry - Defines dataset categories for Emergency and Living analysis.
"""
from typing import List, Dict

# Emergency response datasets (includes transport for evacuation)
EMERGENCY_DATASETS = [
    "hospitals",
    "fire_stations",
    "police_stations",
    "blood_banks",
    "airports",
    "metro_stations",
    "train_stations",
]

# Living condition datasets
LIVING_DATASETS = [
    "schools",
    "preschools",
    "universities",
    "daycares",
    "parks",
    "banks",
    "atms",
    "post_offices",
    "petrol_pumps",
    "metro_stations",
    "train_stations",
    "airports",
    "hospitals",  # Also relevant for living conditions
]

# Weights for scoring (must sum to 1.0 per category)
EMERGENCY_WEIGHTS: Dict[str, float] = {
    "hospitals": 0.25,
    "fire_stations": 0.18,
    "police_stations": 0.18,
    "blood_banks": 0.09,
    "airports": 0.08,
    "metro_stations": 0.10,
    "train_stations": 0.12,  # Important for evacuation
}

LIVING_WEIGHTS: Dict[str, float] = {
    "hospitals": 0.10,
    "schools": 0.12,
    "parks": 0.08,
    "banks": 0.07,
    "atms": 0.05,
    "metro_stations": 0.10,
    "train_stations": 0.10,
    "petrol_pumps": 0.05,
    "universities": 0.06,
    "preschools": 0.06,
    "daycares": 0.06,
    "post_offices": 0.05,
    "airports": 0.05,
}

# Distance thresholds for scoring (in km)
DISTANCE_SCORES = [
    (2.0, 100),    # < 2km = Excellent
    (5.0, 80),     # 2-5km = Good
    (10.0, 60),    # 5-10km = Fair
    (20.0, 40),    # 10-20km = Poor
    (float('inf'), 20),  # > 20km = Very Poor
]

# Grade thresholds
GRADE_THRESHOLDS = [
    (80, "A"),
    (60, "B"),
    (40, "C"),
    (20, "D"),
    (0, "F"),
]


def get_datasets_for_type(analysis_type: str) -> List[str]:
    """Get list of datasets for the given analysis type."""
    if analysis_type == "emergency":
        return EMERGENCY_DATASETS
    elif analysis_type == "living":
        return LIVING_DATASETS
    else:
        raise ValueError(f"Unknown analysis type: {analysis_type}")


def get_weights_for_type(analysis_type: str) -> Dict[str, float]:
    """Get weights for the given analysis type."""
    if analysis_type == "emergency":
        return EMERGENCY_WEIGHTS
    elif analysis_type == "living":
        return LIVING_WEIGHTS
    else:
        raise ValueError(f"Unknown analysis type: {analysis_type}")


def calculate_distance_score(distance_km: float) -> int:
    """Calculate score based on distance to facility."""
    for threshold, score in DISTANCE_SCORES:
        if distance_km < threshold:
            return score
    return 20


def calculate_grade(score: float) -> str:
    """Calculate grade based on overall score."""
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"
