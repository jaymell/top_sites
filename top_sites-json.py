#!/usr/bin/python

""" simple test to see if I can get list of top 100 websites from google,
	dig them, whois them, then use that data to plot their locations on
	a map """

import requests
from HTMLParser import HTMLParser
import subprocess
import shlex
import re
import pprint
from geopy.geocoders import *
import geojson

class Site_Parser(HTMLParser):
        def __init__(self):
                self.reset()
		self.results = [] 
		self.tr_match = False
		self.td_count = 0
		self.last_data = ''
        def handle_starttag(self, tag, attrs):
		if tag == 'tr':
			self.tr_match = True
		elif self.tr_match and tag == 'td':
			self.td_count += 1
	def handle_data(self, data):
		if self.tr_match and self.td_count == 2:
			self.results.append(self.last_data)
		self.last_data = data
	def handle_endtag(self, tag):
		if tag == 'tr':
			self.tr_match = False
			self.td_count = 0

def dig(site):
	""" dig it """
	cmd='dig %s +short' % site
	proc=subprocess.Popen(shlex.split(cmd),stdout=subprocess.PIPE)
	out,err=proc.communicate()
	# return list of IPs:
	return out.split()
	
def get_address(ip):
	""" Using whois """
	#whois 63.96.4.58 | egrep '(^Address|^City|^StateProv|^PostalCode|^Country)'
	def get_match(element, line):
		match = re.match('^%s:\s+(.*)' % element, line, re.IGNORECASE)
		return match.group(1) if match else None
	cmd='whois %s' % ip
	proc=subprocess.Popen(shlex.split(cmd),stdout=subprocess.PIPE)
	out,err=proc.communicate()
	address = ''
	city = ''
	state = ''
	postal = ''
	country = ''
	line = out
	for line in out.split('\n'):	
		match = get_match('Address', line)
		if match: address = match
		match = get_match('City', line)
		if match: city = match
		match = get_match('StateProv', line)
		if match: state = match
		match = get_match('PostalCode', line)
		if match: postal = match
		match = get_match('Country', line)
		if match: country = match
		return_address = ' '.join((address, city, state, postal, country))
	return return_address

def get_coords(address, geolocator):
	""" use geolocator to get coordinates from address """
	try:
		location = geolocator.geocode(address)
		latitude = location.latitude
		longitude = location.longitude
	except Exception as e:
		#print('Failed to get geolocation for %s\n\terror: %s' % (address, e))
		return (None, None)
	else:
		return(latitude, longitude)

# retrieve site:
def get_site(site):
	r = requests.get(site)
	return r.content
	
def get_geojson(site_list):
	""" does the actual process of iterating through sites, getting
		all the necessary info from them and building a geojson
		feature_list, which is returned -- could definitely be
		further functionalized """
	ips = {}
	# to convert to geojson:
	feature_list = []
	for site in site_list:
		# stripping out any newlines should not leave a blank element:
		if len(site.rstrip()): 
			# get all IPs returned by dig, loop through them:
			for ip in dig(site):
				# if ip hasn't already been whois'd:
				if ip not in ips:
					address = get_address(ip)
					latitude, longitude = get_coords(address, geolocator)
					ips[ip] = { 'address': address, 'latitude': latitude, 'longitude': longitude }
				else:
					print('Already done: %s' % ip)
				# if the values of lat/long are not None:
				if ips[ip]['latitude'] and ips[ip]['longitude']:
					# still not sure why google wants long/lat in the order that it does:
					feature = geojson.Feature(geometry=geojson.Point((ips[ip]['longitude'],ips[ip]['latitude'])), properties={'site': site}) 
					feature_list.append(feature)
					feature_collection = geojson.FeatureCollection(feature_list)
					# write feature_collection with each iteration to file:
				else:
					print('No data found: %s' % ip)
	return feature_collection


site = 'http://en.wikipedia.org/wiki/List_of_most_popular_websites'
site = get_site(site)
	
parser = Site_Parser()
parser.feed(site)
site_list = parser.results

geolocator = OpenMapQuest()

# get geojson data from site_list:
feature_collection = get_geojson(site_list)
# write to file:
out_file = './top_sites-json.json'
with open(out_file, 'w') as f:
	geojson.dump(feature_collection, f)

# site
## ip's
### addresses
### coordinates
# a feature is a single coordinate that has a site associated with it
# a featureCollection is basically an array of features
