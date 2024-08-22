# OpenUSD Conan recipe

This is a recipe I made for building a Conan package for [OpenUSD](https://openusd.org). I have only
tested it on my Fedora machine with Conan 2.4.1, and it probably won't work on Windows or Mac
without some modification.

`depproc.py` is used to generate dependency information for all of the components, and will need to
be updated to support e.g. *hgiMetal* for mac.