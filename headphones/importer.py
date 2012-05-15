from lib.pyItunes import *

import time
import os

from lib.beets.mediafile import MediaFile

import headphones

from headphones import logger
from headphones import helpers
from headphones import models
from headphones import mb
from headphones import albumart
from headphones import lastfm


various_artists_mbid = '89ad4ac3-39f7-470e-963a-56509c546377'


# See if the artist is already in the database.
def artistAlreadyTracked(mb_id):
  myDB = db.DBConnection()
  artists = myDB.select('SELECT ArtistID, ArtistName from artists WHERE mb_id=?', [mb_id])

  if any(mb_id in x for x in artists):
    return True
  else:
    return False


def artistNamesToMusicBrainzIds(artistlist):
  for artist in artistlist:
    mb_id = artistNameToMusicBrainzID(artist)

    # Add to database if it doesn't exist
    if mb_id != various_artists_mbid and not artistAlreadyTracked(mb_id):
      addArtisttoDB(mb_id)

    # Just update the tracks if it does
    # else:
    #   myDB = db.DBConnection()
    #   havetracks = len(myDB.select('SELECT TrackTitle from tracks WHERE mb_id=?', [mb_id])) + len(myDB.select('SELECT TrackTitle from have WHERE ArtistName like ?', [artist]))
    #   myDB.action('UPDATE artists SET HaveTracks=? WHERE ArtistID=?', [havetracks, mb_id])

  # Update the similar artist tag cloud:
  logger.info('Updating artist information from Last.fm')

  try:
    lastfm.getSimilar()
  except Exception, e:
    logger.warn('Failed to update arist information from Last.fm: %s' % e)


def artistNameToMusicBrainzID(artist_name):
  artist_name = unicode(artist_name, 'utf-8')
  artist = mb.findArtist(artist_name, limit=1)

  if not artist:
    logger.info('No results found for: %s' % artist_name)

    return None
  else:
    return artist[0]['id']

  # try:
  #   music_brainz_id = artist[0]['id']
  # except IndexError:
  #   logger.info('MusicBrainz query turned up no matches for: %s' % artist_name)


def addArtisttoDB(mb_id, extrasonly=False):
  # Can't add various artists - throws an error from MB
  if mb_id == various_artists_mbid:
    logger.warn('Cannot import Various Artists.')
    return

  myDB = db.DBConnection()
  artist = mb.getArtist(mb_id, extrasonly)

  if not artist:
    return

  if artist['artist_name'].startswith('The '):
    sortname = artist['artist_name'][4:]
  else:
    sortname = artist['artist_name']

  logger.info(u"Now adding/updating: " + artist['artist_name'])
  controlValueDict = {"ArtistID":   mb_id}
  newValueDict = {
    "ArtistName":     artist['artist_name'],
    "ArtistSortName": sortname,
    "DateAdded":      helpers.today(),
    "Status":         "Loading"
  }

  if headphones.INCLUDE_EXTRAS:
    newValueDict['IncludeExtras'] = 1

  myDB.upsert("artists", newValueDict, controlValueDict)

  for rg in artist['releasegroups']:
    rgid = rg['id']
    # check if the album already exists
    rg_exists = myDB.select("SELECT * from albums WHERE AlbumID=?", [rg['id']])

    try:
      release_dict = mb.getReleaseGroup(rgid)
    except Exception, e:
      logger.info('Unable to get release information for %s - there may not be any official releases in this release group' % rg['title'])
      continue

    if not release_dict:
      continue

    logger.info(u"Now adding/updating album: " + rg['title'])
    controlValueDict = { "AlbumID": rg['id'] }

    if len(rg_exists):
      newValueDict = { "AlbumASIN": release_dict['asin'], "ReleaseDate": release_dict['releasedate'] }

    else:
      newValueDict = {"ArtistID":     mb_id,
        "ArtistName":   artist['artist_name'],
        "AlbumTitle":   rg['title'],
        "AlbumASIN":    release_dict['asin'],
        "ReleaseDate":  release_dict['releasedate'],
        "DateAdded":    helpers.today(),
        "Type":         rg['type'],
        "Status":       "Wanted"
      }

    myDB.upsert("albums", newValueDict, controlValueDict)

    try:
      lastfm.getAlbumDescription(rg['id'], artist['artist_name'], rg['title'])
    except Exception, e:
      logger.error('Attempt to retrieve album description from Last.fm failed: %s' % e)

    # I changed the albumid from releaseid -> rgid, so might need to delete albums that have a releaseid
    for release in release_dict['releaselist']:
      myDB.action('DELETE from albums WHERE AlbumID=?', [release['releaseid']])
      myDB.action('DELETE from tracks WHERE AlbumID=?', [release['releaseid']])

    for track in release_dict['tracks']:
      cleanname = helpers.cleanName(artist['artist_name'] + ' ' + rg['title'] + ' ' + track['title'])

      controlValueDict = {"TrackID": track['id'], "AlbumID": rg['id']}
      newValueDict = {"ArtistID": mb_id,
        "ArtistName":     artist['artist_name'],
        "AlbumTitle":     rg['title'],
        "AlbumASIN":      release_dict['asin'],
        "TrackTitle":     track['title'],
        "TrackDuration":  track['duration'],
        "TrackNumber":    track['number'],
        "CleanName":      cleanname
      }

      match = myDB.action('SELECT Location, BitRate from have WHERE CleanName=?', [cleanname]).fetchone()

      if not match:
        match = myDB.action('SELECT Location, BitRate from have WHERE ArtistName LIKE ? AND AlbumTitle LIKE ? AND TrackTitle LIKE ?', [artist['artist_name'], rg['title'], track['title']]).fetchone()
      if not match:
        match = myDB.action('SELECT Location, BitRate from have WHERE TrackID=?', [track['id']]).fetchone()     
      if match:
        newValueDict['Location'] = match['Location']
        newValueDict['BitRate'] = match['BitRate']
        myDB.action('DELETE from have WHERE Location=?', [match['Location']])

      myDB.upsert("tracks", newValueDict, controlValueDict)

  latestalbum = myDB.action('SELECT AlbumTitle, ReleaseDate, AlbumID from albums WHERE ArtistID=? order by ReleaseDate DESC', [mb_id]).fetchone()
  totaltracks = len(myDB.select('SELECT TrackTitle from tracks WHERE ArtistID=?', [mb_id]))
  havetracks = len(myDB.select('SELECT TrackTitle from tracks WHERE ArtistID=? AND Location IS NOT NULL', [mb_id])) + len(myDB.select('SELECT TrackTitle from have WHERE ArtistName like ?', [artist['artist_name']]))

  controlValueDict = {"ArtistID":   mb_id}

  if latestalbum:
    newValueDict = {"Status":       "Active",
            "LatestAlbum":    latestalbum['AlbumTitle'],
            "ReleaseDate":    latestalbum['ReleaseDate'],
            "AlbumID":      latestalbum['AlbumID'],
            "TotalTracks":    totaltracks,
            "HaveTracks":   havetracks}
  else:
    newValueDict = {"Status":     "Active",
            "TotalTracks":    totaltracks,
            "HaveTracks":   havetracks}

  myDB.upsert("artists", newValueDict, controlValueDict)
  logger.info(u"Updating complete for: " + artist['artist_name'])


def addReleaseById(rid):
  myDB = db.DBConnection()

  rgid = None
  artistid = None
  release_dict = None
  results = myDB.select("SELECT albums.ArtistID, releases.ReleaseGroupID from releases, albums WHERE releases.ReleaseID=? and releases.ReleaseGroupID=albums.AlbumID LIMIT 1", [rid])
  for result in results:
    rgid = result['ReleaseGroupID']
    artistid = result['ArtistID']
    logger.debug("Found a cached releaseid : releasegroupid relationship: " + rid + " : " + rgid)
  if not rgid:
    #didn't find it in the cache, get the information from MB
    logger.debug("Didn't find releaseID " + rid + " in the cache. Looking up its ReleaseGroupID")
    try:
      release_dict = mb.getRelease(rid)
    except Exception, e:
      logger.info('Unable to get release information for Release: ' + str(rid) + " " + str(e))
      return
    if not release_dict:
      logger.info('Unable to get release information for Release: ' + str(rid) + " no dict")
      return

    rgid = release_dict['rgid']
    artistid = release_dict['artist_id']

  #we don't want to make more calls to MB here unless we have to, could be happening quite a lot
  rg_exists = myDB.select("SELECT * from albums WHERE AlbumID=?", [rgid])

  #make sure the artist exists since I don't know what happens later if it doesn't
  artist_exists = myDB.select("SELECT * from artists WHERE ArtistID=?", [artistid])

  if not artist_exists and release_dict:
    if release_dict['artist_name'].startswith('The '):
      sortname = release_dict['artist_name'][4:]
    else:
      sortname = release_dict['artist_name']

    logger.info(u"Now manually adding: " + release_dict['artist_name'] + " - with status Paused")
    controlValueDict = {"ArtistID":   release_dict['artist_id']}
    newValueDict = {"ArtistName":     release_dict['artist_name'],
            "ArtistSortName":   sortname,
            "DateAdded":    helpers.today(),
            "Status":       "Paused"}

    if headphones.INCLUDE_EXTRAS:
      newValueDict['IncludeExtras'] = 1

    myDB.upsert("artists", newValueDict, controlValueDict)

  elif not artist_exists and not release_dict:
    logger.error("Artist does not exist in the database and did not get a valid response from MB. Skipping release.")
    return

  if not rg_exists and release_dict:  #it should never be the case that we have an rg and not the artist but if it is this will fail
    logger.info(u"Now adding-by-id album (" + release_dict['title'] + ") from id: " + rgid)
    controlValueDict = {"AlbumID":  rgid}

    newValueDict = {"ArtistID":     release_dict['artist_id'],
      "ArtistName":     release_dict['artist_name'],
      "AlbumTitle":   release_dict['rg_title'],
      "AlbumASIN":    release_dict['asin'],
      "ReleaseDate":    release_dict['date'],
      "DateAdded":    helpers.today(),
      "Status":     'Wanted',
      "Type":       release_dict['rg_type']
    }

    myDB.upsert("albums", newValueDict, controlValueDict)

    #keep a local cache of these so that external programs that are adding releasesByID don't hammer MB
    myDB.action('INSERT INTO releases VALUES( ?, ?)', [rid, release_dict['rgid']])

    for track in release_dict['tracks']:
      cleanname = helpers.cleanName(release_dict['artist_name'] + ' ' + release_dict['rg_title'] + ' ' + track['title'])

      controlValueDict = {"TrackID": track['id'], "AlbumID": rgid}
      newValueDict = {"ArtistID":   release_dict['artist_id'],
        "ArtistName":     release_dict['artist_name'],
        "AlbumTitle":   release_dict['rg_title'],
        "AlbumASIN":    release_dict['asin'],
        "TrackTitle":   track['title'],
        "TrackDuration":  track['duration'],
        "TrackNumber":    track['number'],
        "CleanName":    cleanname
      }

      match = myDB.action('SELECT Location, BitRate from have WHERE CleanName=?', [cleanname]).fetchone()

      if not match:
        match = myDB.action('SELECT Location, BitRate from have WHERE ArtistName LIKE ? AND AlbumTitle LIKE ? AND TrackTitle LIKE ?', [release_dict['artist_name'], release_dict['rg_title'], track['title']]).fetchone()

      if not match:
        match = myDB.action('SELECT Location, BitRate from have WHERE TrackID=?', [track['id']]).fetchone()

      if match:
        newValueDict['Location'] = match['Location']
        newValueDict['BitRate'] = match['BitRate']
        myDB.action('DELETE from have WHERE Location=?', [match['Location']])

      myDB.upsert("tracks", newValueDict, controlValueDict)

    #start a search for the album
    import searcher
    searcher.searchNZB(rgid, False)
  elif not rg_exists and not release_dict:
    logger.error("ReleaseGroup does not exist in the database and did not get a valid response from MB. Skipping release.")
    return
  else:
    logger.info('Release ' + str(rid) + " already exists in the database!")

