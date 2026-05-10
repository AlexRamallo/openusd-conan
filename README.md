This my personal Conan recipe for OpenUSD that I use for my projects. It works for me, but probably
won't work for you.

This is unaffiliated with the [existing PR](https://github.com/conan-io/conan-center-index/pull/24506)
to add OpenUSD to Conan Center.

* `all/conanfile.py` builds an OpenUSD package from source
* `system/conanfile.py` lets you reuse an existing installation of OpenUSD without building it again

# Using the system version

The recipe [system/conanfile.py](system/conanfile.py) builds an empty conan package that lets you
use an existing local installation of openusd, with a similar interface to the
[all/conanfile.py](all/conanfile.py) version. To use it, set the environment variable `OPENUSD_PATH`
to point to the OpenUSD installation folder before calling `conan install` for a consumer package.

Example:

```sh
export OPENUSD_PATH=/opt/openusd/v26.05
conan install ...
```

# Using depproc.py

depproc.py will parse `pxrTargets.cmake` to generate the `_auto_info` function, which you should
copy and paste to the end of the conanfile. This is used for package_info to populate components.

This sucks and is hacky, but it works good enough for now. 

1. Clone the OpenUSD source code somewhere and checkout the correct version

2. Conan install and configure this recipe with as many options enabled as possible

```
cd ~/Repos/OpenUSD
conan install <...>/recipes/openusd/all/conanfile.py -of=BUILD --version=25.02a --build=missing -pr:h=default -pr:b=default
cmake . -G "Unix Makefiles" -DCMAKE_TOOLCHAIN_FILE=BUILD/build/Debug/generators/conan_toolchain.cmake  -DCMAKE_POLICY_DEFAULT_CMP0091=NEW -DCMAKE_BUILD_TYPE=Debug
```

3. Run depproc.py on the generated pxrTargets.cmake file

```
python <...>/recipes/openusd/all/depproc.py ./pxrTargets.cmake
```

4. Copy and paste output to conanfile.py

5. Cross your fingers and export the package