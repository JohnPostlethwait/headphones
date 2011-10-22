import os
import glob

from lib.beets.mediafile import MediaFile

import headphones
from headphones import db, logger, helpers, importer



def libraryScan(dir=None):
  # Now check empty file paths to see if we can find a match based on their folder format
  tracks = myDB.select('SELECT * from tracks WHERE Location IS NULL')
  for track in tracks:
    release = myDB.action('SELECT * from albums WHERE AlbumID=?', [track['AlbumID']]).fetchone()

    try:
      year = release['ReleaseDate'][:4]
    except TypeError:
      year = ''

    artist = release['ArtistName'].replace('/', '_')
    album = release['AlbumTitle'].replace('/', '_')

    if release['ArtistName'].startswith('The '):
      sortname = release['ArtistName'][4:]
    else:
      sortname = release['ArtistName']

    if sortname.isdigit():
      firstchar = '0-9'
    else:
      firstchar = sortname[0]

    lowerfirst = firstchar.lower()
    albumvalues = { 'artist': artist,
      'album':  album,
      'year':   year,
      'first':  firstchar,
      'lowerfirst': lowerfirst
    }

    folder = helpers.replace_all(headphones.FOLDER_FORMAT, albumvalues)
    folder = folder.replace('./', '_/').replace(':','_').replace('?','_')

    if folder.endswith('.'):
      folder = folder.replace(folder[len(folder)-1], '_')

    if not track['TrackNumber']:
      tracknumber = ''
    else:
      tracknumber = '%02d' % track['TrackNumber']

    trackvalues = { 'tracknumber':  tracknumber,
      'title':    track['TrackTitle'],
      'artist':   release['ArtistName'],
      'album':    release['AlbumTitle'],
      'year':     year
    }

    new_file_name = helpers.replace_all(headphones.FILE_FORMAT, trackvalues).replace('/','_') + '.*'
    new_file_name = new_file_name.replace('?','_').replace(':', '_')
    full_path_to_file = os.path.normpath(os.path.join(headphones.MUSIC_DIR, folder, new_file_name)).encode(headphones.SYS_ENCODING, 'replace')
    match = glob.glob(full_path_to_file)

    if match:
      logger.info('Found a match: %s. Writing MBID to metadata' % match[0])

      unipath = unicode(match[0], headphones.SYS_ENCODING, errors='replace')

      myDB.action('UPDATE tracks SET Location=? WHERE TrackID=?', [unipath, track['TrackID']])
      myDB.action('DELETE from have WHERE Location=?', [unipath])

      # Try to insert the appropriate track id so we don't have to keep doing this
      try:
        f = MediaFile(match[0])
        f.mb_trackid = track['TrackID']
        f.save()
        myDB.action('UPDATE tracks SET BitRate=? WHERE TrackID=?', [f.bitrate, track['TrackID']])

        logger.debug('Wrote mbid to track: %s' % match[0])
      except:
        logger.error('Error embedding track id into: %s' % match[0])
        continue

  logger.info('Done checking empty filepaths')
  logger.info('Done syncing library with directory: %s' % dir)

  # Clean up the new artist list
  unique_artists = {}.fromkeys(new_artists).keys()
  current_artists = myDB.select('SELECT ArtistName, ArtistID from artists')
  artist_list = [f for f in unique_artists if f.lower() not in [x[0].lower() for x in current_artists]]

  # Update track counts
  logger.info('Updating track counts')

  for artist in current_artists:
    havetracks = len(myDB.select('SELECT TrackTitle from tracks WHERE ArtistID like ? AND Location IS NOT NULL', [artist['ArtistID']])) + len(myDB.select('SELECT TrackTitle from have WHERE ArtistName like ?', [artist['ArtistName']]))
    myDB.action('UPDATE artists SET HaveTracks=? WHERE ArtistID=?', [havetracks, artist['ArtistID']])

  logger.info('Found %i new artists' % len(artist_list))

  if len(artist_list):
    if headphones.ADD_ARTISTS:
      logger.info('Importing %i new artists' % len(artist_list))
      importer.artistNamesToMusicBrainzIds(artist_list)
    else:
      logger.info('To add these artists, go to Manage->Manage New Artists')
      headphones.NEW_ARTISTS = artist_list

  if headphones.DETECT_BITRATE:
    headphones.PREFERRED_BITRATE = sum(bitrates)/len(bitrates)/1000