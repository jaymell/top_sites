#!/usr/bin/python

""" simple test to see if I can get list of top 100 websites from google,
	dig them, whois them, then use that data to plot their locations on
	a map """

# map.data.loadGeoJson('http://localhost/top_sites-json.json')

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
	
def get_locale(ip):
	""" Using whois --- currently leaving out street address and zip
		code in attempt to improve overall accuracy """
	#whois 63.96.4.58 | egrep '(^Address|^City|^StateProv|^PostalCode|^Country)'
	def get_match(element, line):
		match = re.match('^%s:\s+(.*)' % element, line, re.IGNORECASE)
		return match.group(1) if match else None
	cmd='whois %s' % ip
	proc=subprocess.Popen(shlex.split(cmd),stdout=subprocess.PIPE)
	out,err=proc.communicate()
	#address = ''
	city = ''
	state = ''
	#postal = ''
	country = ''
	line = out
	for line in out.split('\n'):	
		#match = get_match('Address', line)
		#if match: address = match
		match = get_match('City', line)
		if match: city = match
		match = get_match('StateProv', line)
		if match: state = match
		#match = get_match('PostalCode', line)
		#if match: postal = match
		match = get_match('Country', line)
		if match: country = match
		#return_address = ' '.join((address, city, state, postal, country))
		return_address = ' '.join((city, state, country))
	return return_address

def get_coords(address, geolocator):
	""" use geolocator to get coordinates from address
		--- needs to be significantl redesigned to:
		1) consult multiple geolocators, randomly?
		2) reconcile potential diffs between them
	 """
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
	
def get_geojson_features(site):
	""" takes a site dict and returns a list of geojson features 
		corresponding to each IP in the site
		--- SKIPS the ip if no coords found """
	feature_list = []
	for ip in site:
		if site[ip]['latitude'] and site[ip]['longitude']:
			# still not sure why google wants long/lat in the order that it does:
			feature = geojson.Feature(geometry=geojson.Point((site[ip]['longitude'],site[ip]['latitude'])), properties={'site': site}) 
			feature_list.append(feature)
			feature_collection = geojson.FeatureCollection(feature_list)
		else:
			print('No data found: %s' % ip)
	return feature_list

if __name__ == '__main__':
	
	import pprint
	from pymongo import MongoClient

	site = 'http://en.wikipedia.org/wiki/List_of_most_popular_websites'
	site = get_site(site)
		
	parser = Site_Parser()
	parser.feed(site)
	# save results to list and strip out newlines ...
	site_list = [ i for i in parser.results if i != '\n' ]
			
	# db stuff -- create following automagic if they don't 
	# already exist:
	MONGODB_HOST = 'localhost'
	MONGODB_PORT = 27017
	DB_NAME = 'top_sites'
	COLLECTION_NAME = 'sites'
	connection = MongoClient(MONGODB_HOST, MONGODB_PORT)
	collection = connection[DB_NAME][COLLECTION_NAME]
	

	# declare ip dict to store IPs as they are dug, so they're
	# not dug twice by different sites:
	ips = {}
	#site_dict = {}
	geolocator = OpenMapQuest()

	for site in site_list:
		# remove slashes from site names:
		site = site.replace('/','')
		site_dict = {}
		site_key = site.replace('.','_')
		site_dict[site_key] = {}

		for ip in dig(site):

			# avoid digging twice:
			# and check against underscores, not dots, cuz mongo is stupid
			ip_key = ip.replace('.','_')

			if ip_key not in ips: 
				address = get_locale(ip)
				latitude, longitude = get_coords(address, geolocator)
				ips[ip_key] = { 'address': address, 'latitude': latitude, 'longitude': longitude }

			site_dict[site_key][ip_key] = ips[ip_key]

		print('site: %s' % site)
		pprint.pprint(site_dict[site_key])	
		
		# insert site into db:
		#site_id = collection.insert_one(site_dict[site]).inserted_id
		site_id = collection.insert_one(site_dict).inserted_id

	# this current broken ... need to figuure out how to build
	# feature list and collection cleanly but don't care right now ...
	# not sure I structured the geojson properly in the first place:
	"""
	feature_list = [ get_geojson_feature(i) for i in site_dict ]	
	# get geojson data from site_list:
	feature_collection = geojson.FeatureCollection(feature_list)
	# write to file:
	out_file = './top_sites-json.json'
	with open(out_file, 'w') as f:
		geojson.dump(feature_collection, f)
	"""
