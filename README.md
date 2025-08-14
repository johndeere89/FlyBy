# FlyBy
Python script to spot airplanes nearby

Create your ADS-B setup as described on this page:
https://www.flightaware.com/adsb/piaware/build/

Also create a FlightAware AeroAPI account.

Because you are an ADS-B feeder, you will be able to make $10 worth of free API calls every month.

Download the files from this repository and put them on your Raspberry Pi.

Make sure you unzip logos.zip.

Install Pillow and Requests with:
pip install pillow requests

Fill in your API token in main.py at:
AEROAPI_TOKEN =

Determine your location via https://boundingbox.klokantech.com/ and enter it under

=== Flight Area Configuration ===

Example:
MIN_LAT = 52.61889
MAX_LAT = 52.79250
MIN_LON = 4.97778
MAX_LON = 5.30306

Tip: Use ChatGPT to convert the result from BoundingBox.
