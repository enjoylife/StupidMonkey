StupidMonkey
============
----
A student project diving into understanding api's and the data storage / manipulation involved. Text analysis and graphical views of the results. And improving code readability for the future me.

Requirements
============

* [Evernote python sdk][evernote]
* [mongodb][pymongo]
* [pattern][pattern]
* [d3.js][d3]


Thoughts on the project
============

Im using evernote's thrift binary(efficient?) interface to their api's, which is different then the json and xml interchange of most. Alot of popular api interaction involves the understanding of the file like hierarchy and  restfull principles for multiple meaning urls. With the thrift layer it is like utilizing a package, and you forget the http involved, which in a way feels as though it makes me think about the code differently. How much it effects the code development I don't fully understand yet. Maybe it protects you from more drastic api changes on each end? 

Documenting code, whether it be because it is some complex process which you probably will forget, or for future reference, takes some skill in it's own right. To explain the right details out of a 50 step problem without verbosely describing the actions clearly marked practice. Some times a comment you think might help sounds good inititally, but then you comeback and it does no help whatsoever. Had alot of those moments.  I definitly had to rethink what should have been done in the first place.



[evernote]: https://github.com/evernote/evernote-sdk-python
[pymongo]: https://github.com/mongodb/mongo-python-driver
[pattern]: http://www.clips.ua.ac.be/pages/pattern
[d3]: https://github.com/mbostock/d3/wiki