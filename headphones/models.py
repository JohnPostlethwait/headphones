from headphones import logger

from lib import peewee


peewee.database.connect()


class Artist(peewee.Model):
  id =                peewee.PrimaryKeyField()
  name =              peewee.TextField()
  unique_name =       peewee.TextField()
  musicbrainz_id =    peewee.TextField()
  location =          peewee.TextField()
  state =             peewee.TextField()
  added_on =          peewee.DateTimeField()
  updated_on =        peewee.DateTimeField()


class Album(peewee.Model):
  id =                peewee.PrimaryKeyField()
  artist =            peewee.ForeignKeyField(Artist)
  name =              peewee.TextField()
  location =          peewee.TextField()
  type =              peewee.TextField()
  musicbrainz_id =    peewee.TextField()
  release_group_id =  peewee.TextField()
  asin =              peewee.TextField()
  state =             peewee.TextField()
  released_on =       peewee.DateTimeField()
  added_on =          peewee.DateTimeField()
  updated_on =        peewee.DateTimeField()

  # def tracks():
  #   peewee.ForeignKeyField(Track)


class Track(peewee.Model):
  id =          peewee.PrimaryKeyField()
  album =       peewee.ForeignKeyField(Album)
  number =      peewee.IntegerField()
  title =       peewee.TextField()
  length =      peewee.IntegerField()
  location =    peewee.TextField()
  state =       peewee.TextField()
  updated_on =  peewee.DateTimeField()
  added_on =    peewee.DateTimeField()
