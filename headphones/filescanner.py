# -*- coding: utf-8 -*-

import os
import glob
import datetime
import time
import lib.threadpool as ThreadPool

from lib.beets.mediafile import MediaFile

import headphones

from headphones import db
from headphones import musicbrainz
from headphones import logger
from headphones import helpers

from lib.musicbrainz2 import utils

# Todo: MAKE ALL OF THIS RUN WITHOUT EXCEPTION UPON INTERNET DISCONNECTION!

def scan():
  logger.info(u"Now scanning the music library located at %s." % unicode(headphones.MUSIC_DIR, errors="ignore"))

  connection = db.DBConnection()

  for dirpath, dirnames, filenames in os.walk( headphones.MUSIC_DIR ):
    logger.debug(u'Now scanning the directory "%s"' % unicode(dirpath, errors="ignore"))

    # Scan all of the files in this directory:
    for filename in filenames:
      # Only scan music files...
      if any( filename.lower().endswith('.' + x.lower()) for x in headphones.MEDIA_FORMATS ):
        logger.debug(u'Now scanning the file "%s"' % unicode(filename, errors="ignore"))

        full_path = os.path.join( dirpath, filename )

        # Try to read the tags from the file, move on if we can't.
        try:
          media_file = MediaFile( full_path )
        except Exception, e:
          logger.debug(u'Cannot read tags of file "%s" because of the exception "%s"' % (unicode(filename, errors="ignore"), str(e)))
          break

        # If we did read the tags, but the artist can't be found, move on to the next file...
        if media_file.albumartist:
          id3_artist = media_file.albumartist
        elif media_file.artist:
          id3_artist = media_file.artist
        else:
          break

        logger.debug(u'Found the artist name "%s" in the ID3 tag of "%s" file.' % (id3_artist, unicode(full_path, errors="ignore")))

        artist_path_parts = []

        for part in dirpath.split('/'):
          artist_path_parts.append( part )

          if id3_artist.lower() in part.lower(): break

        if artist_path_parts:
          artist_path = os.sep.join( artist_path_parts )
        else:
          artist_path = headphones.MUSIC_DIR

        # If we already have this artist in the DB only add their releases, 
        # we do not need to re-add them to the Music Library.
        tracked_artist = connection.action('SELECT artist_id FROM artists WHERE artist_name = "' + id3_artist + '"').fetchone()

        if tracked_artist:
          logger.debug(u'Artist name "%s" is already tracked by Headphones, moving on...' % id3_artist)

          ThreadPool.put( addReleases, { 'artist_id': tracked_artist['artist_id'] } )

          break
        else:
          artist_record = addArtist( id3_artist, artist_path )
          artist_id     = artist_record['artist_id']

          ThreadPool.put( addReleases, { 'artist_id': artist_id } )

          break


def addArtist( id3_artist_name, path ):
  connection          = db.DBConnection()
  musicbrainz_artist  = musicbrainz.getBestArtistMatch( id3_artist_name )
  print str(id3_artist_name)
  print str(musicbrainz_artist)
  connection.action('INSERT INTO artists (artist_name, artist_unique_name, \
      artist_sort_name, artist_location, artist_state, artist_mb_id) VALUES(?, ?, ?, ?, ?, ?)',
      [ id3_artist_name, musicbrainz_artist.getUniqueName(),
      musicbrainz_artist.getSortName(), path, 'wanted', utils.extractUuid(musicbrainz_artist.id)])

  artist_record = connection.action('SELECT * FROM artists WHERE artist_mb_id = ?', [utils.extractUuid(musicbrainz_artist.id)]).fetchone()

  return artist_record


def addReleases( artist_id, update_artist = True ):
  print "ARTIST ID IS: '" + str(artist_id) + "'"

  connection          = db.DBConnection()
  artist_record       = connection.action('SELECT artist_name FROM artists WHERE artist_id = ?', (artist_id,)).fetchone()
  musicbrainz_artist  = musicbrainz.getBestArtistMatch( artist_record['artist_name'] )
  release_ids         = []
  print str(musicbrainz_artist)
  for release in musicbrainz_artist.getReleases():
    release_ids.append( utils.extractUuid(release.id) )

  # These release results do not contain all the information, we must re-query for that info... (Grumble, grumble – Crappy API.)
  for rid in release_ids:
    release = musicbrainz.getRelease( rid )
    release_group_id = utils.extractUuid(release.getReleaseGroup().id)
    release_group_tracked = connection.action('SELECT * FROM albums WHERE album_release_group_id = ?', [release_group_id]).fetchone()

    if release_group_tracked: continue

    connection.action( 'INSERT INTO albums (album_mb_id, album_asin, album_release_group_id, \
        artist_id, album_name, album_type, album_released_on, album_state) VALUES(?, ?, ?, ?, ?, ?, ?, ?)',
        [ rid, release.getAsin(), release_group_id, artist_id, release.getTitle(), 
        'album', release.getEarliestReleaseDate(), 'wanted' ] )

    release_record = connection.action('SELECT * FROM albums WHERE album_mb_id = ?', [rid]).fetchone()

    track_number = 1

    for track in release.getTracks():
      track_record = connection.action('INSERT INTO tracks (album_id, track_number, \
      track_title, track_length, track_state) VALUES(?, ?, ?, ?, ?)',
      [ release_record['album_id'], track_number, track.getTitle(), track.getDuration(), 'wanted'])

      track_number += 1

  # Rescan the Music Library after adding new releases to see if the user has 
  # them or not. Will not run if explicitly told not to by the caller.
  if(update_artist): ThreadPool.put( updateArtist, { 'artist_id': artist_id } )


# Rescan the directory structure for a given artist ID, updating the album 
# states, and track locations and states as we go... For now, assume all 
# missing tracks and albums are "wanted".
# 
# Change this later to respect the state set by the user on the individual 
# artist/album/track level.
def updateArtist( artist_id ):
  connection  = db.DBConnection()
  artist      = connection.action('SELECT artist_location FROM artists WHERE artist_id = ?', [artist_id]).fetchone()

  if artist:
    for dirpath, dirnames, filenames in os.walk( artist['artist_location'] ):
      logger.debug(u'Now scanning the directory "%s"' % dirpath)

      # Scan all of the files in this directory:
      for filename in filenames:
        # Only scan music files...
        if any( filename.lower().endswith('.' + x.lower()) for x in headphones.MEDIA_FORMATS ):
          full_path = os.path.join( dirpath, filename )

          # Try to read the tags from the file, move on if we can't.
          try:
            media_file = MediaFile( full_path )

            connection.action("UPDATE tracks SET track_location=?, track_status=? WHERE album_id IN \
                (SELECT album_id FROM albums WHERE album_name LIKE ? AND artist_id IN \
                (SELECT artist_id FROM artists WHERE artist_id=?)) AND track_number=?",
                (full_path, 'have', media_file.album, artist_id, media_file.track))
          except Exception, e:
            logger.debug(u'Cannot read tags of file "%s" because of the exception "%s"' % (filename, str(e)))
            continue

    artist_albums = connection.action('SELECT album_id FROM albums WHERE artist_id=?', (artist_id))

    for album in artist_albums:
      album_complete = True # Assuming it is complete is easier...
      tracks = connection.action('SELECT track_id, track_location FROM tracks WHERE album_id=?', (album['album_id']))

      for track in tracks:
        if track['track_location'] == None:
          connection.action('UPDATE tracks SET track_state=? WHERE track_id = ?', ('wanted', track['track_id']))
          album_complete = False

      # If we have all of the tracks for this album, set the state of the 
      # album to 'have', otherwise we will set them to 'wanted'.
      # 
      # There could be a bug here that if we set the album state to 'wanted'
      # the corresponding, missing tracks might not be set to 'wanted' as well.
      # 
      # Investigate this later...
      album_state = 'have' if album_complete else 'wanted'

      connection.action('UPDATE albums SET album_state=? WHERE album_id=?', ('have', album['album_id']))
  else:
    logger.info(u"Could not find an artist in the database with the artist_id of %s" % artist_id)


def updateMissingTrackPaths():
  logger.info('Ensuring that all of the tracks that Headphones is tracking are all still in the Music Library.')

  connection  = db.DBConnection()
  tracks      = connection.select('SELECT id, location from tracks WHERE location IS NOT NULL')

  for track in tracks:
    if not os.path.isfile( track['location'].encode(headphones.SYS_ENCODING) ):
      logger.info('Track ID ' + str(track['id']) + ' is no longer in the music library, clearing location.')

      connection.action('UPDATE tracks SET location=?, bitrate=?, state="wanted" WHERE id=?', [None, None, track['id']])

  logger.info('Done ensuring all of the tracks are still in the Music Library.')


def __ensureLibraryLocation__():
  if not os.path.isdir( headphones.MUSIC_DIR ):
    logger.warn(u'Cannot find the directory "%s" Not scanning.' % unicode(headphones.MUSIC_DIR, errors='ignore'))

    return False
  else:
    return True
