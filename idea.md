﻿#StupidMonkey

##Abstract
The ways to visualize your thoughts are not very innovative. Boring notes and simple tabular like tools do not convey as much information as actually is hidden within a persons notes. I propose a more fluid, creative and insightful approach by utilizing dynamic visualizations of not just plain notes and small amounts of meta data. No, far more than just the standard user input, I want to highlight the hidden connections between things like note semantics, topic interest, and history of oneself recorded in their evernotes. 


##Problem Definition
> “Defines what the problem is without any reference to possible solutions” -Code Complete

The understanding of how continued note taking and learning new things progresses oneself's knowledge. How that relates over time is too difficult to track and visualize. People learn without realizing what their learning and how that changes over time.__Current ways to visualize and infer knowledge from notes are terrible__.


##Solution:
> “All progress is precarious, and the solution of one problem brings us face to face with another problem.” -Martin Luther King, Jr.

Utilizing the storage and synchronization capabilities as well as a large user base of Evernote users, create a dynamic web based application that shows users detailed analysis of what the have taken notes of. Primarily focusing on the ease of discovering things about oneself through already Taken notes, and wiki like databases. Inoder to fully expose that analysis create clear, intuitive, and engaing visualizations to display this extra knowledge.


##Keys to remember:
> “Its the little details that are vital. Little things make big things happen -John Wooden

* Intuitive in it's design.
* Displays logical layouts of a persons notes, notebooks and content.
* Fast to display, must not have user feel as though time is wasted.
* Easily customize-able in its feel and look, or at least appears that way to the user.
* User can search through introspected data as well as flow through it's temporal nature if appropriate.
* Colorful and attractive visualizations that transition within a couple of seconds.
* Easily navigable options for customization.
* Transparent policies on user data.
* Compatibility within all modern browsers.

##Requirements:
> "Describe in detail what the program is going to do” -Code Complete 

* Hierarchical clustering displaying the connections from the different notebooks, to the tags contained in them to finally the notes that are connected to the tags.
* clickable portions of note content that can be searched by outside sources, wikipedia, etc.
* Treemap repersentation of analytics, wordcount, number of notes per tag, notebook, etc.


##System Overview:
> If you can’t explain something to a six-year-old, you really don’t understand it yourself.” -Albert Einstein

Back-end must be a high performance server, with load balancing and a plethora of options for tweaking performance. Nginx would work well for a balancer between multiple Cherrypy apps.
D3.js provides the necessary visualization tools and comes with data loading tools as well. A bonus is that D3.js has plenty of preexisting examples to build up from.
Python bindings will be used for interacting with the Evernote Thrift API.
Redis will be used for site analytic data and caching.
Analytic processing will be done with effective easy to develop  machine learning tools. Scikit-learn is an easy off the shelf approach, with minimal tweaking relative to other low level machine learning libraries. Pattern is also a very good text and easy to use lib, very good for initial prototyping.
### Inference
* __Time Based__
  * wordcount
  * grammer level or readability metric
  * word importance: nouns, verbs, etc...
  * topic summaries
* __Non Time Based__
  * comparing between: notes, tags, notebooks
  * outside knowledge: querying wikipedia, duckduckgo, freebase...
* __Other__
  * wordcounts
  * averages: note length, time deltas of new notes, 
  * top note taking locations
