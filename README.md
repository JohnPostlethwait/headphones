#![preview thumb](https://github.com/JohnPostlethwait/headphones/raw/master/data/images/headphoneslogo.png)Headphones

###Installation and Notes

This is a pretty early release of a third-party add-on for SABnzbd.

To run it, just double-click the Headphones.py file (in Windows - you may need to right click and click 'Open With' -> Python) or launch a terminal, cd into the Headphones directory and run 'python headphones.py'.

For additional startup options, type 'python Headphones.py -h' or 'python Headphones.py --help'

###Screenshots
First Run

![preview thumb](http://img502.imageshack.us/img502/7814/screenshot20111102at115a.png)


There are still a few things that I'm working on:

* Post-processing doesn't work yet. Just use the categories setting with SABnzbd to customize your final download directory.

* Importing your music library takes a long time. That's because for each artist, it tries to find all of their releases before moving on to the next artist. I might stagger how the info gets added, i.e. first it adds all the artists, then it goes back and adds all of their release information.

* "Snatched" downloads don't change status to "Downloaded". I'm keeping a database of snatched downloads, but since post-processing doesn't work yet, I didn't want to change the status until the app knows for sure that the album has downloaded.


If you run into any more issues, visit http://github.com/JohnPostlethwait/headphones and report an issue. 

This is free software so feel free to use it/modify it as you wish. 

If you have any ideas for the next release, also make sure to post that here!