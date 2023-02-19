#!python3
# coding=utf-8
from datetime import date
import time
import re
import urllib.request, urllib.error, urllib.parse
from bs4 import BeautifulSoup
import psycopg2
import lirc
import pafy
import vlc
from subprocess import call
import os


DIR_ROOT = '/mnt/onetouch/audio'
URL_ROOM = 'http://192.168.0.110:8000/stream.mp3'
VOL_STEP = 10
POS_STEP = 10000


class remotesource:
	def __init__(self):
		lirc.init("mypiradio", "/etc/lirc/mypiradio_iconbit.lircrc")

	def getnextcode(self):
		return ''.join(lirc.nextcode())


class keyboardsource:
	def getnextcode(self):
		return input("enter the command (play, pause, stop or station code): ")


class pg_storage:
	def __init__(self):
		self._conn = psycopg2.connect("dbname=enteryourname")
		self._cur = self._conn.cursor()

	def reset_book_settings(self, subdir):
		self._cur.execute('update public.settings set value_ = %s where name = %s', ('0', 'audiobook_time'))
		self._cur.execute('update public.settings set value_ = %s where name = %s', ('0', 'audiobook_file_index'))
		self._cur.execute('update public.settings set value_ = %s where name = %s', (subdir, 'audiobook_subdir_name'))
		self._conn.commit()

	def is_new_book(self, subdir):
		self._cur.execute('select value_ from public.settings where name = %s', ('audiobook_subdir_name',))
		oldsubdir = self._cur.fetchone()[0]
		return oldsubdir != subdir

	def save_time(self, time1, idx1):
		self._cur.execute('update public.settings set value_ = %s where name = %s', (time1, 'audiobook_time'))
		self._cur.execute('update public.settings set value_ = %s where name = %s', (idx1, 'audiobook_file_index'))
		self._conn.commit()

	def load_time(self):
		self._cur.execute('select value_ from public.settings where name = %s', ('audiobook_time',))
		time2 = max([int(self._cur.fetchone()[0]) - 10000, 0])
		self._cur.execute('select value_ from public.settings where name = %s', ('audiobook_file_index',))
		idx2 = int(self._cur.fetchone()[0])
		return idx2, time2

	def get_station_name(self, station):
		self._cur.execute("select name from public.radio_stations where code = %s", (station,))
		return self._cur.fetchone()


class soyuz_site:
	def __init__(self, root, prefixes):
		self._root = root
		self._prefixes = prefixes

	def get_stream(self, url_code):
		url_prefix = self._prefixes.get(url_code)
		print(self._root + url_prefix)
		result = None
		html_root = urllib.request.urlopen(self._root + url_prefix).read().decode("utf-8")
		if html_root is None:
			return result
		htmlroot_obj = BeautifulSoup(html_root, "html.parser")
		htmldates_obj = htmlroot_obj.find_all("div", {"class":"program-guide__anons"})
		if not htmldates_obj:
			return result
		htmlcurrdate_obj = htmldates_obj[0]
		pageurl = self._root + htmlcurrdate_obj.find("a").get("href")
		html = urllib.request.urlopen(pageurl).read().decode("utf-8")
		r = re.compile(r"youtube.com/embed/([a-zA-Z0-9_\-]+)\?", re.IGNORECASE)
		r_result = r.search(html)
		if r_result is None:
			return result
		youtube_url = r_result.group(1)
		print(youtube_url)
		return self.find_youtube_stream(youtube_url)

	def find_youtube_stream(self, url):
		video = pafy.new(url)
		print(video)
		best = video.getbestaudio()
		return best.url


class streaming_sites:
	def __init__(self, map):
		self._map = map

	def get(self, code):
		return self._map.get(code)


class radioplayer:
	def __init__(self, stor, sites):
		self._storage = stor
		self._sites = sites
		self._list = None
		self._medialist = None
		self._code = None
		self._player = vlc.Instance().media_list_player_new()
		self._baseplayer = vlc.Instance().media_player_new()
		print("Player initialized")

	def position_increase(self):
		if not self._player.is_playing():
			return
		pos = self._player.get_media_player().get_time()
		len = self._player.get_media_player().get_length()
		if pos is None or pos == -1:
			return
		if (len is None or len == -1) or (pos + POS_STEP < len):
			self._player.get_media_player().set_time(pos + POS_STEP)

	def position_decrease(self):
		if not self._player.is_playing():
			return
		pos = self._player.get_media_player().get_time()
		len = self._player.get_media_player().get_length()
		if pos is None or pos == -1:
			return
		if (len is None or len == -1) or (pos - POS_STEP > 0):
			self._player.get_media_player().set_time(pos - POS_STEP)

	def volume_increase(self):
		if not self._player.is_playing():
			return
		vol = self._player.get_media_player().audio_get_volume()
		print(vol)
		if vol <= 100 - VOL_STEP:
			self._player.get_media_player().audio_set_volume(vol + VOL_STEP)
		else:
			self._player.get_media_player().audio_set_volume(100)

	def volume_decrease(self):
		if not self._player.is_playing():
			return
		vol = self._player.get_media_player().audio_get_volume()
		print(vol)
		if vol >= VOL_STEP:
			self._player.get_media_player().audio_set_volume(vol - VOL_STEP)
		else:
			self._player.get_media_player().audio_set_volume(0)

	def set_code(self, code):
		self._code = code

	def code(self):
		return self._code

	def is_new_book(self, subdir):
		return self._storage.is_new_book(subdir)

	def reset_book_settings(self, subdir):
		self._storage.reset_book_settings(subdir)

	def is_book_playing(self):
		return self._player.is_playing() and self._baseplayer.get_media().get_mrl().find('/audio/book') != -1

	def save_time(self):
		time1 = self._baseplayer.get_time()
		idx1 = self._medialist.index_of_item(self._baseplayer.get_media())
		self._storage.save_time(time1, idx1)

	def load_time(self):
		return self._storage.load_time()

	def set_file_list(self, root, files):
		self._list = []
		for f in files:
			self._list.append(os.path.join(root, f))

	def play_from_dir(self, dir_prefix):
		dir_base = os.path.join(DIR_ROOT, dir_prefix)
		subdir_base_nopath = sorted(os.listdir(dir_base))[0]
		subdir_base = os.path.join(dir_base, subdir_base_nopath)
		if dir_prefix == 'book' and self.is_new_book(subdir_base_nopath):
			self.reset_book_settings(subdir_base_nopath)
		self.set_file_list(subdir_base, sorted(os.listdir(subdir_base)))
		self.play_list()

	def jump_next_file(self):
		self._player.next()

	def jump_next_dir(self):
		subdir = os.path.dirname(self._list[0])
		dir = os.path.dirname(subdir)
		subdir_list = sorted(os.listdir(dir))
		idx = subdir_list.index(os.path.basename(subdir))
		if idx == len(subdir_list)-1:
			subdir = os.path.join(dir, subdir_list[0])
		else:
			subdir = os.path.join(dir, subdir_list[idx+1])
		self.set_file_list(subdir, sorted(os.listdir(subdir)))
		self.play_list()

	def jump_previous_file(self):
		self._player.previous()

	def jump_previous_dir(self):
		subdir = os.path.dirname(self._list[0])
		dir = os.path.dirname(subdir)
		subdir_list = sorted(os.listdir(dir))
		idx = subdir_list.index(os.path.basename(subdir))
		if idx == 0:
			subdir = os.path.join(dir, subdir_list[len(subdir_list)-1])
		else:
			subdir = os.path.join(dir, subdir_list[idx-1])
		self.set_file_list(subdir, sorted(os.listdir(subdir)))
		self.play_list()

	def play_from_site(self, site_code, url_code):
		site = self._sites.get(site_code)
		if (site is not None):
			stream = site.get_stream(url_code)
			if (stream is not None):
				self._list = [stream]
				self.play_list()

	def setstation(self, station):
		stationname = self._storage.get_station_name(station)
		if stationname is not None:
			self._list = [stationname[0]]
			self.play_list()

	def play_room(self):
		self._list = [URL_ROOM]
		self.play_list()

	def play_list(self):
		if self._medialist != None:
			self._medialist.release()
		self._player.release()
		self._player = vlc.Instance().media_list_player_new()
		self._player.set_media_player(self._baseplayer)
		self._medialist = vlc.Instance().media_list_new(self._list)
		self._player.set_media_list(self._medialist)
		idx = 0
		time = 0
		if self._list[0].find('/audio/book') != -1:
			idx, time = self.load_time()
		self._player.play_item_at_index(idx)
		self._baseplayer.set_time(time)
		print("playing " + self._list[idx] + " at " + str(time) + "...")

	def pause(self):
		print("paused...")
		self._player.pause()

	def stop(self):
		print("stopped...")
		self._player.stop()
		self._list = None


def get_sites():
	return streaming_sites({
		"soyuz" : soyuz_site(
			"https://tv-soyuz.ru", {
				"apostol" : "/Chitaem-Apostol",
				"evangelie" : "/peredachi/chitaem-evangelie-vmeste-s-tserkovyu",
				"calendar" : "/peredachi/tserkovnyy-kalendar-propoved-na-kazhdyy-den",
				"todayinfo" : "/Etot-den-v-istorii",
				"orthead" : "/Pravoslavnyy-na-vsyu-golovu"
			})
	})

def get_storage():
	return pg_storage()

_radioplayer = None
def get_player():
	global _radioplayer
	if _radioplayer is None:
		_radioplayer = radioplayer(get_storage(), get_sites())
	return _radioplayer

_source = None
def get_source():
	global _source
	if _source is None:
		_source = remotesource()
       	#_source = keyboardsource()
	return _source

def changeradio():
	source = get_source()
	previous_time = time.time()
	while 1:
		try:
			code = source.getnextcode()
			print(code)
			player = get_player()
			print(player)
			current_time = time.time()
			print(current_time)
			if current_time - previous_time < 1:
				continue
			previous_time = current_time
			if code == "volume_increase":
				player.volume_increase()
				continue
			if code == "volume_decrease":
				player.volume_decrease()
				continue
			if code == "position_increase":
				player.position_increase()
				continue
			if code == "position_decrease":
				player.position_decrease()
				continue
			if player.is_book_playing() and code not in ("left", "right", "up", "down"):
				player.save_time()
			if code == "pause":
				player.pause()
			elif code == "stop":
				player.stop()
			#elif code == "poweroff":
				#call("sudo poweroff", shell=True)
			elif ":" in code:
				site_code, url_code = code.split(":", 2)
				player.play_from_site(site_code, url_code)
			elif code in ("green","red","blue","yellow","book"):
				player.play_from_dir(code)
			elif code == "up":
				player.jump_next_dir()
			elif code == "down":
				player.jump_previous_dir()
			elif code == "right":
				player.jump_next_file()
			elif code == "left":
				player.jump_previous_file()
			elif code == "room":
				player.play_room()
			else:
				player.setstation(code)
		except Exception as e:
			print(e)
			pass
			#TODO play sound and write to log


changeradio()
