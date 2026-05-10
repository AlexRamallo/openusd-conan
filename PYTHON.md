# Python version

* OpenUSD has optional components that use Python
* They add a dependency on Boost::Python AND the Python packages PySide6 and PyOpenGL (available on pip)
* The boost package is linked against a particular python interpreter version (3.12, 3.13, etc)
* The OpenUSD package won't work properly if installed on a system with a different interpreter

