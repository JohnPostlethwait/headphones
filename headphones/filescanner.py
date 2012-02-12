import os
import glob
import datetime
import time

from multiprocessing.pool import ThreadPool

from lib.beets.mediafile import MediaFile

import headphones

from headphones import db
from headphones import musicbrainz
from headphones import logger
from headphones import helpers

from lib.musicbrainz2 import utils


connection = db.DBConnection()
thread_pool = ThreadPool(4)




def updateArtist( artist_id ):
  artist = connection.action('SELECT artist_location FROM artists WHERE artist_id = ?', [artist_id]).fetchone()

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

            connection.action("UPDATE tracks SET track_location=? WHERE album_id IN \
                (SELECT album_id FROM albums WHERE album_name LIKE ? AND artist_id IN \
                (SELECT artist_id FROM artists WHERE artist_id=?)) AND track_number=?",
                (full_path, media_file.album, artist_id, media_file.track))
          except Exception, e:
            logger.debug(u'Cannot read tags of file "%s" because of the exception "%s"' % (filename, str(e)))
            continue
  else:
    logger.info(u"Could not find an artist in the database with the artist_id of %s" % artist_id)


def scan():
  logger.info(u"Now scanning the music library located at %s." % unicode(headphones.MUSIC_DIR, errors="ignore"))

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

        # If we already have this artist in the DB, continue on, we don't need to scrape them again...
        artist_currently_tracked = connection.action('SELECT artist_id FROM artists WHERE artist_name = "' + id3_artist + '"').fetchone()

        if artist_currently_tracked:
          logger.debug(u'Artist name "%s" is already tracked by Headphones, moving on...' % id3_artist)

          break
        else:
          artist = musicbrainz.getBestArtistMatch( id3_artist )
          artist_record = addArtist( id3_artist, artist, artist_path )

          addReleases( artist, artist_record['artist_id'] )

          thread_pool.map( updateArtist, artist_record['artist_id'] )

          break


def addArtist( id3_name, musicbrainz_artist, path ):
  connection.action('INSERT INTO artists (artist_name, artist_unique_name, \
      artist_sort_name, artist_location, artist_state, artist_mb_id) VALUES(?, ?, ?, ?, ?, ?)',
      [ id3_name, musicbrainz_artist.getUniqueName(),
      musicbrainz_artist.getSortName(), path, 'wanted', utils.extractUuid(musicbrainz_artist.id)])

  artist_record = connection.action('SELECT * FROM artists WHERE artist_mb_id = ?', [utils.extractUuid(musicbrainz_artist.id)]).fetchone()

  return artist_record


def addReleases( musicbrainz_artist, artist_id ):
  release_ids = []
  releases_db_ids = []

  for release in musicbrainz_artist.getReleases():
    release_ids.append( utils.extractUuid( release.id ) )

  # These release results do not contain all the information, we must re-query for that info...
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

    releases_db_ids.append( release_record['album_id'] )

    track_number = 1

    for track in release.getTracks():
      track_record = connection.action('INSERT INTO tracks (album_id, track_number, \
      track_title, track_length, track_state) VALUES(?, ?, ?, ?, ?)',
      [ release_record['album_id'], track_number, track.getTitle(), track.getDuration(), 'wanted'])

      track_number += 1

  return releases_db_ids


def updateMissingTrackPaths():
  logger.info('Ensuring that all of the tracks that Headphones is tracking are all still in the Music Library.')

  tracks = connection.select('SELECT id, location from tracks WHERE location IS NOT NULL')

  for track in tracks:
    if not os.path.isfile( track['location'].encode(headphones.SYS_ENCODING) ):
      logger.info('Track ID ' + str(track['id']) + ' is no longer in the music library, clearing location.')

      connection.action('UPDATE tracks SET location=?, bitrate=?, state="wanted" WHERE id=?', [None, None, track['id']])

  logger.info('Done ensuring all of the tracks are still in the Music Library.')



def __ensureLibraryLocation__():
  if not os.path.isdir( headphones.MUSIC_DIR ):
    logger.warn('Cannot find the directory "%s" Not scanning.' % headphones.MUSIC_DIR)

    return False
  else:
    return True


# def __trackHasChanged__(location, bitrate):
#   if connection.action( 'SELECT id FROM tracks WHERE location="?" AND bitrate=?', [location, bitrate] ).fetchone():
#     return False
#   else:
#     return True
