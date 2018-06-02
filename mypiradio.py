#!python2
# coding=utf-8

from datetime import date
import re
import urllib2
import psycopg2
import lirc
import vlc
from subprocess import call
import os

months = ['yanvarya', 'fevralya', 'marta', 'aprelya', 'maya', 'iyunya', 'iyulya', 'avgusta', 'sentyabrya', 'oktyabrya', 'noyabrya', 'dekabrya']
dir_root = '/mnt/onetouch/audio'
url_room = 'http://192.168.0.110:8000/stream.mp3'

class radioplayer:
	_conn = None
	_cur = None
	_player = None
	_baseplayer = None
	_list = None
	_medialist = None

	def __init__(self):
		self._conn = psycopg2.connect("dbname=mypiserver")
		self._cur = self._conn.cursor()
		self._player = vlc.Instance().media_list_player_new()
		self._baseplayer = vlc.Instance().media_player_new()

	def is_new_book(self, subdir):
                self._cur.execute('select value_ from public.settings where name = %s', ('audiobook_subdir_name',))
                oldsubdir = self._cur.fetchone()[0]
		return oldsubdir != subdir

	def reset_book_settings(self, subdir):
		self._cur.execute('update public.settings set value_ = %s where name = %s', ('0', 'audiobook_time'))
		self._cur.execute('update public.settings set value_ = %s where name = %s', ('0', 'audiobook_file_index'))
		self._cur.execute('update public.settings set value_ = %s where name = %s', (subdir, 'audiobook_subdir_name'))
		self._conn.commit()
			
	def is_book_playing(self):
		return self._player.is_playing() and self._baseplayer.get_media().get_mrl().find('/audio/book') != -1

	def save_time(self):
		time1 = self._baseplayer.get_time()
		idx1 = self._medialist.index_of_item(self._baseplayer.get_media())
		print idx1
		print time1
		self._cur.execute('update public.settings set value_ = %s where name = %s', (time1, 'audiobook_time'))
		self._cur.execute('update public.settings set value_ = %s where name = %s', (idx1, 'audiobook_file_index'))
		self._conn.commit()

	def load_time(self):
		self._cur.execute('select value_ from public.settings where name = %s', ('audiobook_time',))
		time2 = max([int(self._cur.fetchone()[0]) - 10000, 0])
		self._cur.execute('select value_ from public.settings where name = %s', ('audiobook_file_index',))
		idx2 = int(self._cur.fetchone()[0])
		return idx2, time2

	def set_file_list(self, root, files):
		self._list = []
		for f in files:
			self._list.append(os.path.join(root, f))

	def play_from_dir(self, dir_prefix):
		dir_base = os.path.join(dir_root, dir_prefix)
		subdir_base_nopath = os.listdir(dir_base)[0]
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

	def play_from_soyuz(self, url_prefix):
		today = date.today()
		pageurl = '{0}-{1}-{2}-{3}'.format(
			url_prefix, today.strftime("%-d"), months[today.month - 1], today.strftime("%Y"))
		html = urllib2.urlopen(pageurl).read()
		r = re.compile(r"http:.+[.]mp3")
		r_result = r.search(html)
		if r_result is not None:
			self._list = [r_result.group().replace(' ', '%20')]
			self.play_list()		

	def play_apostol(self):
		self.play_from_soyuz('http://tv-soyuz.ru/peredachi/chitaem-apostol')

	def play_evangelie(self):
		self.play_from_soyuz('http://tv-soyuz.ru/peredachi/chitaem-evangelie-vmeste-s-tserkovyu')

	def play_calendar(self):
		self.play_from_soyuz('http://tv-soyuz.ru/peredachi/tserkovnyy-kalendar')

	def setstation(self, station):
		self._cur.execute("select name from public.radio_stations where code = %s", (station,))
		stationname = self._cur.fetchone()
		if stationname is not None:
			self._list = [stationname[0]]
			self.play_list()		

	def play_room(self):
		self._list = [url_room]
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
		print "playing " + self._list[idx] + " at " + str(time) + "..."

	def pause(self):
		print "paused..."
		self._player.pause()

	def stop(self):
		print "stopped..."
		self._player.stop()
		self._list = None

class controlsource:
	def getnextcode(self):
		pass

class remotesource(controlsource):
	def __init__(self):
		lirc.init("mypiradio")

	def getnextcode(self):
		return ''.join(lirc.nextcode())
	
class keyboardsource(controlsource):
	def getnextcode(self):
		return raw_input("enter the command (play, pause, stop or station code): ")
		
def changeradio():
	player = radioplayer()
	source = remotesource()
	#source = keyboardsource()
	while 1:
		code = source.getnextcode()
                if player.is_book_playing() and code not in ("left", "right", "up", "down"):
                        player.save_time()
		if code == "pause":	
			player.pause()
		elif code == "stop":
			player.stop()
		#elif code == "poweroff":
			#call("sudo poweroff", shell=True)
		elif code == "apostol":
			player.play_apostol()
		elif code == "evangelie":
			player.play_evangelie()
		elif code == "calendar":
			player.play_calendar()
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

def main():
	changeradio()		
			
main()	
