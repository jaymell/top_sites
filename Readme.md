## Synopsis
Simple P.O.C. script to get locales/coordinates from IP addresses and populate
a Mongo collection with them so data can be used by other projects. Parses 
entries from Wikipedia's top 50 website list; gets IP addresses from the 
URLs via dig; uses whois to get locale; uses geopy module to convert
locales to coordinates. 

## Motivation
Primary goal is to build an IP geolocation dataset for visualization with Google Maps / d3.js

## Dependencies
See requirements.txt -- use 'pip install -r requirements.txt' to install them

## Future improvements
1. Alternative implementations for geolocating:
  * cycle through alternative geocoders if no results found on the default
  * use paid service -- e.g., https://www.maxmind.com/en/geoip2-precision-services
2. More up-to-date source for top websites, e.g., http://www.alexa.com/topsites, this would 
allow for time dimension as the list changes

