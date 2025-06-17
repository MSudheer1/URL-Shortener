from enum import Enum

class ExpirationUnitEnum(str, Enum):
    minutes = "minutes"
    hours = "hours"
    days = "days"
    months = "months"
    years = "years"
