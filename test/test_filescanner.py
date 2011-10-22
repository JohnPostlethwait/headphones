import sys

sys.path.append( '/Users/johnpostlethwait/Documents/workspace/headphones/' )

import unittest
import headphones

from headphones import filescanner




class TestFilescanner(unittest.TestCase):
  def setUp(self):
    headphones.MUSIC_DIR = '.'


  def test_ensureFilePaths(self):
    self.assertEqual( None, filescanner.ensureFilePaths() )


  def test__ensureLibraryLocation__for_a_good_location(self):
    self.assertTrue( filescanner.__ensureLibraryLocation__() )

  def test__ensureLibraryLocation__for_a_bad_location(self):
    headphones.MUSIC_DIR = '/I/DO/NOT/EXIST'
    self.assertFalse( filescanner.__ensureLibraryLocation__() )



if __name__ == '__main__':
  unittest.main()
