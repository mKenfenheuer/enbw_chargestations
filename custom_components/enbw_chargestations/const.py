"""Constants for the EnBW charge stations component."""

DOMAIN = "enbw_chargestations"

# Config entry keys
STATION_NUMBER = "station_number"
NAME = "name"
LOCATION = "location"
API_KEY = "api_key"

DEG_PER_KM = 1 / 111

# Default radius of the search area on the map, in meters.
DEFAULT_SEARCH_RADIUS_M = 5000

# How many of the nearest stations to offer in the search results.
MAX_SEARCH_RESULTS = 50

# Extra state attribute keys
ATTR_CABLE_ATTACHED = "cableAttached"
ATTR_PLUG_TYPE_NAME = "plugTypeName"
ATTR_MAX_POWER_IN_KW = "maxPowerInKw"
ATTR_MAX_POWER_PER_PLUG_TYPE_IN_KW = "maxPowerInKwPerPlugType"
ATTR_EVSE_ID = "evseId"
ATTR_STATE = "state"
ATTR_STATION_ID = "stationid"
ATTR_LATITUDE = "latitude"
ATTR_LONGITUDE = "longitude"
ATTR_ADDRESS = "address"
ATTR_UPDATED_AT = "updatedAt"
ATTR_AVAILABLE_CHARGE_POINTS = "availableChargePoints"
ATTR_TOTAL_CHARGE_POINTS = "totalChargePoints"
ATTR_OUT_OF_SERVICE = "isOutOfService"
