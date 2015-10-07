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
import pycountry

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

def dig(site, results=None):
	""" dig it """

	cmd='dig %s +short' % site
	proc=subprocess.Popen(shlex.split(cmd),stdout=subprocess.PIPE)
	out,err=proc.communicate()
	if not results: results = []
	for line in out.split():
		# regex match for ip address:
		match = re.match('^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$',line)
		if match:
			results.append(line)	
		else: 
			""" If not an IP address, assume it's a CNAME
				and call function recursively """
			#dig(line, results)
			pass
	return results
	
def get_locale(ip):
	""" Using whois --- currently leaving out street address and zip
		code in attempt to improve overall accuracy , basically this from 
		command line: """ #whois 63.96.4.58 | egrep '(^City|^StateProv|^Country)'
	def get_match(element, line):
		match = re.match('^%s:\s+(.*)' % element, line, re.IGNORECASE)
		return match.group(1) if match else None
	cmd='whois %s' % ip
	proc=subprocess.Popen(shlex.split(cmd),stdout=subprocess.PIPE)
	out,err=proc.communicate()
	city = ''
	state = ''
	country = ''
	line = out
	for line in out.split('\n'):	
		match = get_match('City', line)
		if match: city = match
		match = get_match('StateProv', line)
		if match: state = match
		match = get_match('Country', line)
		if match: country = match
		return_address = ' '.join((city, state, country))
	return return_address

def get_coords(address, geolocator):
	""" use geolocator to get coordinates from address
		--- potential redesign to:
		1) consult multiple geolocators, randomly?
		2) reconcile potential diffs between them
	 """
	try:
		location = geolocator.geocode(address)
		latitude = location.latitude
		longitude = location.longitude
	except Exception as e:
		print('Failed to get geolocation for %s\n\terror: %s' % (address, e))
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
			feature = geojson.Feature(geometry=geojson.Point((site[ip]['longitude'],site[ip]['latitude'])), properties={'site': site}) 
			feature_list.append(feature)
			feature_collection = geojson.FeatureCollection(feature_list)
		else:
			print('No data found: %s' % ip)
	return feature_list

if __name__ == '__main__':
	
	import pprint
	import ConfigParser
	from pymongo import MongoClient
	
	site = 'http://en.wikipedia.org/wiki/List_of_most_popular_websites'
	site = get_site(site)
		
	site_parser = Site_Parser()
	site_parser.feed(site)
	# save results to list and strip out newlines ...
	site_list = [ i for i in site_parser.results if i != '\n' ]
			
	# source db config from external file:
	config = 'mongo.cfg'
	defaults = {'MONGODB_HOST': 'localhost', 'MONGODB_PORT': '27017', 'DB_NAME': 'top_sites', 'COLLECTION_NAME': 'top_sites'}
	config_parser = ConfigParser.SafeConfigParser(defaults)
	config_parser.read(config)

	try:
		MONGODB_HOST = config_parser.get('DB', 'MONGODB_HOST')
		MONGODB_PORT = int(config_parser.get('DB', 'MONGODB_PORT'))
		DB_NAME = config_parser.get('DB', 'DB_NAME')
		COLLECTION_NAME = config_parser.get('DB', 'COLLECTION_NAME')
	except Exception as e:
		print('Error assigning DB variables: %s' % e)
		exit(1)
	else:
		connection = MongoClient(MONGODB_HOST, MONGODB_PORT)
		collection = connection[DB_NAME][COLLECTION_NAME]
	

	# declare ip dict to store IPs as they are dug, so they're
	# not dug twice by different sites:
	ips = {}

	# OpenMapQuest() returning 403 Forbidden
	#geolocator = OpenMapQuest()
	geolocator = Nominatim()

	site_json = []

	for site in site_list:
		# remove slashes from site names:
		site = site.replace('/','')
		site_dict = {}
		site_dict['url'] = site
		site_dict['ips'] = []

		for ip in dig(site):
			# avoid digging twice:
			if ip not in ips: 
				address = get_locale(ip)
				# get country from address:
				try:
                                        # make uppercase:
                                        two_letter = address.split()[-1].upper()
                                except Exception as e:
                                        print('FAILED: ',e,address)
                                else:
                                        country = pycountry.countries.get(alpha2=two_letter)
                                        three_letter = country.alpha3
                                        country = three_letter
				latitude, longitude = get_coords(address, geolocator)
				ip_dict = {'ip': ip, 'country': country, 'address': address, 'latitude': latitude, 'longitude': longitude } 
				site_dict['ips'].append(ip_dict)
				ips[ip] = ip_dict
			else:
				site_dict['ips'].append(ips[ip])

		pprint.pprint(site_dict)	
		
		# insert site into db:
		try:
			site_id = collection.insert_one(site_dict).inserted_id
		except Exception as e:
			print('Failed to write to database: %s \n\t Entry: %s' % (e,site_dict))	

