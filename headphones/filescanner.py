import os
import glob
import datetime
import time

from lib.beets.mediafile import MediaFile

import lib.discogs as discogs

import headphones

from headphones import db
from headphones import logger
from headphones import helpers

connection = db.DBConnection()
discogs.user_agent = 'Headphones/0.0.1 +https://github.com/JohnPostlethwait/headphones'




# Stub method for updating the library.
def updateArtists():
  return None


def scan():
  logger.info(u"Now scanning the music library located at %s." % unicode(headphones.MUSIC_DIR, errors="ignore"))

  for dirpath, dirnames, filenames in os.walk( headphones.MUSIC_DIR ):
    logger.debug(u'Now scanning the directory "%s"' % unicode(dirpath, errors="ignore"))

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
          continue

        # If we did read the tags, but the artist can't be found, move on to the next file...
        if media_file.albumartist:
          id3_artist = media_file.albumartist
        elif media_file.artist:
          id3_artist = media_file.artist
        else:
          continue

        logger.debug(u'Found the artist name "%s" in the ID3 tag of "%s" file.' % (id3_artist, unicode(full_path, errors="ignore")))

        # If we already have this artist in the DB, continue on, we don't need to scrape them again...
        artist_currently_tracked = connection.action('SELECT artist_id FROM artists WHERE artist_clean_name=?', [helpers.cleanName(id3_artist)]).fetchone()

        if artist_currently_tracked:
          logger.debug(u'Artist name "%s" is already tracked by Headphones, moving on...' % id3_artist)
          break
        else:
          # Scrape the Artist from Discogs Database, move on if we cannot...
          try:
            artist = discogs.Artist( id3_artist )
            artist_info = artist.data
            image_url = None
            image_small_url = None

            # Loop through all of the artist images and select the "primary" one for storage in the DB.
            if artist_info.get('images'):
              for i in artist_info['images']:
                if i['type'] != 'primary':
                  image_url = i['uri']
                  image_small_url = i['uri150']
                  break

            artist_record = connection.action('INSERT INTO artists (artist_name, artist_clean_name, artist_image_url, artist_small_image_url, artist_location, artist_state) VALUES(?, ?, ?, ?, ?, ?)',
                            [artist_info['name'], helpers.cleanName(artist_info['name']), image_url, image_small_url, full_path, 'wanted'])

            # getReleases( artist.releases, artist_record['id'] )

          except discogs.HTTPError:
            logger.info(u'No artist with the name "%s" could be found in the Discogs database, skipping...' % id3_artist)
            break



# def getReleases(releases, artist_id):
  # DISCOGS ALBUM API SUCKS, DO THIS LATER.
  # 
  # for release in artist.releases:
  #   release_info = release.data.get('formats')
  #   release_desc = release_info[0].get('descriptions')
  # 
  #   if release_info and release_desc:
  #     is_album = False
  # 
  #     for release_type in release_desc:
  #       # if release_type ==
  # 
  #       connection.action('INSERT INTO albums (discogs_release_id, image_url, artist_id, name, location, type, added_on) VALUES(?, ?, ?, ?, ?, ?, ?)',
  #                   [])
  #   else:
  #     continue


def updateMissingTrackPaths():
  logger.info('Ensuring that all of the tracks that Headphones is tracking are all still in the Music Library.')

  tracks = connection.select('SELECT id, location from tracks WHERE location IS NOT NULL')

  for track in tracks:
    if not os.path.isfile( track['location'].encode(headphones.SYS_ENCODING) ):
      logger.info('Track ID ' + str(track['id']) + ' is no longer in the music library, clearing location.')

      connection.action('UPDATE tracks SET location=?, bitrate=?, state="wanted" WHERE id=?', [None, None, track['id']])

  logger.info('Done ensuring all of the tracks are still in the Music Library.')



def __ensureLibraryLocation__():
  if not os.path.isdir(headphones.MUSIC_DIR):
    logger.warn('Cannot find the directory "%s" Not scanning.' % headphones.MUSIC_DIR)
    return False
  else:
    return True


# def __trackHasChanged__(location, bitrate):
#   if connection.action( 'SELECT id FROM tracks WHERE location="?" AND bitrate=?', [location, bitrate] ).fetchone():
#     return False
#   else:
#     return True
