import os
from pathlib import Path
from conan import ConanFile
from conan.tools.cmake import CMakeToolchain, CMakeDeps, CMake, cmake_layout
from conan.tools.files import copy, get

required_conan_version = ">=2.0.0"

class OpenUSD(ConanFile):
    name = "openusd"
    settings = 'os', 'compiler', 'arch', 'build_type'
    implements = ["auto_shared_fpic"]
    options = {
        'shared': [True, False],
        'fPIC': [True, False],
        'usd': [True, False], # build usd library
        'imaging': [True, False], # build imaging library (hydra stuff)
        'usdimaging': [True, False], # build usdimaging library
        'tools': [True, False], # build the usd command-line tools
        'ptex': [True, False], # enable ptex support for imaging
        'materialx': [True, False], # enable MaterialX support
        'opencolorio': [True, False], # enable OpenColorIO support for imaging
        'openimageio': [True, False], # enable OpenImageIO support for imaging
        'embree': [True, False], # enable embree-based rendering plugin
    }
    default_options = {
        'shared': True,
        'fPIC': False,
        'usd': True,
        'imaging': True,
        'usdimaging': True,
        'tools': True,
        'opencolorio': False,
        'ptex': False,
        'openimageio': False,

        'materialx': True,
        'materialx/*:render': True,
        
        'onetbb/*:tbbmalloc': True,
        'onetbb/*:tbbproxy': True,

        'embree': False,
        'embree/*:with_tbb': True,

        # usd *requires* shared link with boost::python (unless doing monolithic?)
        # see: https://github.com/PixarAnimationStudios/OpenUSD/issues/1087#issuecomment-636100768
        "boost/*:shared": True,
        "boost/*:without_python": False,

        "opensubdiv/*:with_tbb": True,
        "opensubdiv/*:with_opengl": True,
        "opensubdiv/*:with_omp": True,
        "opensubdiv/*:with_cuda": True,
        "opensubdiv/*:with_clew": True,
        "opensubdiv/*:with_opencl": True,
        "opensubdiv/*:with_dx": True,
        "opensubdiv/*:with_metal": True,
    }


    def layout(self):
        cmake_layout(self)


    def do_requires(self, pkg):
        # this calls `self.requires(...)` using relevant configuration specified in conandata.yml
        reqs = self.conan_data[self.version]['requirements']
        assert pkg in reqs
        info = reqs[pkg]
        ver = info['version']
        orig = info['orig']

        if ver != info['orig']:
            self.output.warning(f'OpenUSD/{self.version} upstream expects "{pkg}" version {orig}, but we\'re using version {ver} instead')

        self.requires(
            '%s/%s' % (pkg, ver),
            override = info.get('override', False),
            force = info.get('force', False),
            transitive_headers = info.get('transitive_headers', True),
        )


    def requirements(self):
        self.do_requires('onetbb')

        self.do_requires('opensubdiv')
        self.do_requires('boost')

        if self.options.ptex:
            self.do_requires('ptex')

        if self.options.embree:
            self.do_requires('embree3')

        if self.options.opencolorio:
            self.do_requires('opencolorio')

        if self.options.materialx:
            self.do_requires('materialx')

        if self.settings.os == 'Linux' and self.options.imaging:
            self.requires('xorg/system')
            self.requires('opengl/system')
        
        if self.options.openimageio:
            self.do_requires('openimageio')

        # MISSING
        # self.requires('osl/1.10.9')

        # overrides
        for pkg in self.conan_data[self.version]['overrides']:
            self.requires(pkg, override = True)


    def source(self):
        get(self, **self.conan_data[self.version]["sources"], strip_root=True, destination=self.source_folder)


    def _patch_sources_cmake(self):
        os.remove(Path(self.source_folder)/"cmake"/"modules"/"FindTBB.cmake")
        os.remove(Path(self.source_folder)/"cmake"/"modules"/"FindOpenSubdiv.cmake")
        os.remove(Path(self.source_folder)/"cmake"/"modules"/"FindEmbree.cmake")


    def generate(self):
        tc = CMakeToolchain(self)
        dep = CMakeDeps(self)
        
        tc.variables['BUILD_SHARED_LIBS'] = self.options.shared

        # this helps OpenUSD build scripts find CMake targets from conan dependencies
        # (kind of like aliases for cmake target names)

        tc.variables['TBB_tbb_LIBRARY'] = self.dependencies["onetbb"].cpp_info.get_property('cmake_target_name')

        if self.options.ptex:
            tc.variables['PTEX_LIBRARY'] = self.dependencies["ptex"].cpp_info.get_property('cmake_target_name')

        boost_py_ver = str(self.dependencies["boost"].options.python_version).replace('.', '')
        tc.variables[f'Boost_PYTHON{boost_py_ver}_LIBRARY'] = "Boost::python"

        dep.set_property("opensubdiv", "cmake_additional_variables_prefixes", ["OPENSUBDIV"]) # capitalize the name
        osd_info = self.dependencies["opensubdiv"].cpp_info
        tc.variables['OPENSUBDIV_OSDCPU_LIBRARY'] = osd_info.components['osdcpu'].get_property('cmake_target_name')
        tc.variables['OPENSUBDIV_OSDGPU_LIBRARY'] = osd_info.components['osdgpu'].get_property('cmake_target_name')

        if self.options.embree:
            tc.variables['EMBREE_FOUND'] = True
            dep.set_property("embree3", "cmake_additional_variables_prefixes", ["EMBREE"])
            tc.variables['EMBREE_LIBRARY'] = self.dependencies["embree3"].cpp_info.get_property('cmake_target_name')

        dep.set_property("opencolorio", "cmake_additional_variables_prefixes", ["OCIO"])
        dep.set_property("openimageio", "cmake_additional_variables_prefixes", ["OIIO"])

        tc.generate()
        dep.generate()


    _cmake = None
    def _configure_cmake(self):
        if self._cmake:
            return self._cmake
        self._patch_sources_cmake()
        self._cmake = CMake(self)
        self._cmake.configure(
            variables = {
                'PXR_BUILD_MONOLITHIC': False,

                'PXR_ENABLE_PYTHON_SUPPORT': True,
                'PXR_ENABLE_GL_SUPPORT': True,
                'PXR_ENABLE_VULKAN_SUPPORT': False, # experimental/requires glslang
                'PXR_ENABLE_OSL_SUPPORT': False, # currently, no OSL conan package exists

                'PXR_BUILD_EMBREE_PLUGIN': self.options.embree,
                'PXR_BUILD_PRMAN_PLUGIN': False,
                'PXR_BUILD_ALEMBIC_PLUGIN': False, # TODO conan package exists
                'PXR_BUILD_DRACO_PLUGIN': False, # TODO conan package exists

                'PXR_BUILD_DOCUMENTATION': False,
                'PXR_BUILD_TESTS': False,
                'PXR_BUILD_EXAMPLES': False,
                'PXR_BUILD_TUTORIALS': False,
                
                'PXR_BUILD_IMAGING': self.options.imaging,
                'PXR_BUILD_USD_TOOLS': self.options.tools,
                'PXR_BUILD_USDVIEW': True,
                
                'PXR_ENABLE_PTEX_SUPPORT': self.options.ptex,
                'PXR_ENABLE_MATERIALX_SUPPORT': self.options.materialx,
                'PXR_BUILD_OPENCOLORIO_PLUGIN': self.options.opencolorio,
                'PXR_BUILD_OPENIMAGEIO_PLUGIN': self.options.openimageio,
            }
        )
        return self._cmake


    def build(self):
        cmake = self._configure_cmake()
        self.run(f'cmake --build "{self.build_folder}" --config Release -- -j24')


    def package(self):
        cmake = self._configure_cmake()
        cmake.install()


    def package_info(self):
        self.boost_python_libs = ['boost::python']
        self.tbb_libs = ['onetbb::libtbb', 'onetbb::tbbmalloc']

        self._auto_info()

        p_pkg = Path(self.package_folder)
        self.buildenv_info.prepend_path('PATH', str(p_pkg/'bin'))
        self.buildenv_info.prepend_path('PYTHONPATH', str(p_pkg/'lib'/'python'))

        # embree isn't found by depproc.py, so create the component manually
        if self.options.embree:
            self.cpp_info.components["hdEmbree"].requires = ['plug', 'tf', 'vt', 'gf', 'work', 'hf', 'hd', 'hdx', 'embree3::embree3'] + self.tbb_libs
            self.cpp_info.components["hdEmbree"].libs = [] # hdEmbree is a plugin, not a library

        for c in self.cpp_info.components:
            comp = self.cpp_info.components[c]

            if self.options.ptex:
                comp.requires.append('ptex::ptex')
            
            if self.options.opencolorio:
                comp.requires.append('opencolorio::opencolorio')
            
            if self.options.openimageio:
                comp.requires.append('openimageio::openimageio')

        if self.settings.os == 'Linux':
            self.cpp_info.components["arch"].system_libs = ['m', 'dl']
            gldeps = [
                'opengl::opengl',
                'xorg::x11',
                'xorg::ice',
                'xorg::sm',
                'xorg::xext',
            ]
            self.cpp_info.components["garch"].requires.extend(gldeps)
            self.cpp_info.components["glf"].requires.extend(gldeps)
        else:
            assert f"OS '{self.settings.os}' currently not supported by this recipe"
    

    # this method was automatically generated with "depproc.py" and should not be modified directly
    def _auto_info(self):
        # arch
        self.cpp_info.components["arch"].requires = []
        self.cpp_info.components["arch"].libs = ['usd_arch']
        # tf
        self.cpp_info.components["tf"].requires = ['arch'] + self.boost_python_libs + self.tbb_libs
        self.cpp_info.components["tf"].libs = ['usd_tf']
        # gf
        self.cpp_info.components["gf"].requires = ['arch', 'tf']
        self.cpp_info.components["gf"].libs = ['usd_gf']
        # js
        self.cpp_info.components["js"].requires = ['tf']
        self.cpp_info.components["js"].libs = ['usd_js']
        # trace
        self.cpp_info.components["trace"].requires = ['arch', 'js', 'tf'] + self.boost_python_libs + self.tbb_libs
        self.cpp_info.components["trace"].libs = ['usd_trace']
        # work
        self.cpp_info.components["work"].requires = ['tf', 'trace'] + self.tbb_libs
        self.cpp_info.components["work"].libs = ['usd_work']
        # plug
        self.cpp_info.components["plug"].requires = ['arch', 'tf', 'js', 'trace', 'work'] + self.boost_python_libs + self.tbb_libs
        self.cpp_info.components["plug"].libs = ['usd_plug']
        # vt
        self.cpp_info.components["vt"].requires = ['arch', 'tf', 'gf', 'trace'] + self.boost_python_libs + self.tbb_libs
        self.cpp_info.components["vt"].libs = ['usd_vt']
        # ts
        # skipped
        # ar
        self.cpp_info.components["ar"].requires = ['arch', 'js', 'tf', 'plug', 'vt'] + self.boost_python_libs
        self.cpp_info.components["ar"].libs = ['usd_ar']
        # kind
        self.cpp_info.components["kind"].requires = ['tf', 'plug']
        self.cpp_info.components["kind"].libs = ['usd_kind']
        # sdf
        self.cpp_info.components["sdf"].requires = ['arch', 'tf', 'gf', 'trace', 'vt', 'work', 'ar'] + self.boost_python_libs
        self.cpp_info.components["sdf"].libs = ['usd_sdf']
        # ndr
        self.cpp_info.components["ndr"].requires = ['tf', 'plug', 'vt', 'work', 'ar', 'sdf'] + self.boost_python_libs
        self.cpp_info.components["ndr"].libs = ['usd_ndr']
        # sdr
        self.cpp_info.components["sdr"].requires = ['tf', 'vt', 'ar', 'ndr', 'sdf'] + self.boost_python_libs
        self.cpp_info.components["sdr"].libs = ['usd_sdr']
        # pcp
        self.cpp_info.components["pcp"].requires = ['tf', 'trace', 'vt', 'sdf', 'work', 'ar'] + self.boost_python_libs + self.tbb_libs
        self.cpp_info.components["pcp"].libs = ['usd_pcp']
        # usd
        self.cpp_info.components["usd"].requires = ['arch', 'kind', 'pcp', 'sdf', 'ar', 'plug', 'tf', 'trace', 'vt', 'work'] + self.boost_python_libs + self.tbb_libs
        self.cpp_info.components["usd"].libs = ['usd_usd']
        # usdGeom
        self.cpp_info.components["usdGeom"].requires = ['js', 'tf', 'plug', 'vt', 'sdf', 'trace', 'usd', 'work'] + self.boost_python_libs + self.tbb_libs
        self.cpp_info.components["usdGeom"].libs = ['usd_usdGeom']
        # usdVol
        self.cpp_info.components["usdVol"].requires = ['tf', 'usd', 'usdGeom']
        self.cpp_info.components["usdVol"].libs = ['usd_usdVol']
        # usdMedia
        self.cpp_info.components["usdMedia"].requires = ['tf', 'vt', 'sdf', 'usd', 'usdGeom']
        self.cpp_info.components["usdMedia"].libs = ['usd_usdMedia']
        # usdShade
        self.cpp_info.components["usdShade"].requires = ['tf', 'vt', 'js', 'sdf', 'ndr', 'sdr', 'usd', 'usdGeom']
        self.cpp_info.components["usdShade"].libs = ['usd_usdShade']
        # usdLux
        self.cpp_info.components["usdLux"].requires = ['tf', 'vt', 'ndr', 'sdf', 'usd', 'usdGeom', 'usdShade']
        self.cpp_info.components["usdLux"].libs = ['usd_usdLux']
        # usdProc
        self.cpp_info.components["usdProc"].requires = ['tf', 'usd', 'usdGeom']
        self.cpp_info.components["usdProc"].libs = ['usd_usdProc']
        # usdRender
        self.cpp_info.components["usdRender"].requires = ['gf', 'tf', 'usd', 'usdGeom', 'usdShade']
        self.cpp_info.components["usdRender"].libs = ['usd_usdRender']
        # usdHydra
        self.cpp_info.components["usdHydra"].requires = ['tf', 'usd', 'usdShade']
        self.cpp_info.components["usdHydra"].libs = ['usd_usdHydra']
        # usdRi
        self.cpp_info.components["usdRi"].requires = ['tf', 'vt', 'sdf', 'usd', 'usdShade', 'usdGeom'] + self.boost_python_libs
        self.cpp_info.components["usdRi"].libs = ['usd_usdRi']
        # usdSkel
        self.cpp_info.components["usdSkel"].requires = ['arch', 'gf', 'tf', 'trace', 'vt', 'work', 'sdf', 'usd', 'usdGeom'] + self.boost_python_libs + self.tbb_libs
        self.cpp_info.components["usdSkel"].libs = ['usd_usdSkel']
        # usdUI
        self.cpp_info.components["usdUI"].requires = ['tf', 'vt', 'sdf', 'usd']
        self.cpp_info.components["usdUI"].libs = ['usd_usdUI']
        # usdUtils
        self.cpp_info.components["usdUtils"].requires = ['arch', 'tf', 'gf', 'sdf', 'usd', 'usdGeom', 'usdShade'] + self.boost_python_libs
        self.cpp_info.components["usdUtils"].libs = ['usd_usdUtils']
        # usdPhysics
        self.cpp_info.components["usdPhysics"].requires = ['tf', 'plug', 'vt', 'sdf', 'trace', 'usd', 'usdGeom', 'usdShade', 'work'] + self.boost_python_libs + self.tbb_libs
        self.cpp_info.components["usdPhysics"].libs = ['usd_usdPhysics']
        # usdMtlx
        if self.options.materialx:
            self.cpp_info.components["usdMtlx"].requires = ['arch', 'gf', 'ndr', 'sdf', 'sdr', 'tf', 'vt', 'usd', 'usdGeom', 'usdShade', 'usdUI', 'usdUtils'] + ['materialx::MaterialXCore', 'materialx::MaterialXFormat']
            self.cpp_info.components["usdMtlx"].libs = ['usd_usdMtlx']
        else:
            self.cpp_info.components["usdMtlx"].requires = []
            self.cpp_info.components["usdMtlx"].libs = []
        # garch
        self.cpp_info.components["garch"].requires = ['arch', 'tf']
        self.cpp_info.components["garch"].libs = ['usd_garch']
        # hf
        self.cpp_info.components["hf"].requires = ['plug', 'tf', 'trace']
        self.cpp_info.components["hf"].libs = ['usd_hf']
        # hio
        self.cpp_info.components["hio"].requires = ['arch', 'js', 'plug', 'tf', 'vt', 'trace', 'ar', 'hf']
        self.cpp_info.components["hio"].libs = ['usd_hio']
        # cameraUtil
        self.cpp_info.components["cameraUtil"].requires = ['tf', 'gf']
        self.cpp_info.components["cameraUtil"].libs = ['usd_cameraUtil']
        # pxOsd
        self.cpp_info.components["pxOsd"].requires = ['tf', 'gf', 'vt', 'opensubdiv::osdcpu'] + self.boost_python_libs
        self.cpp_info.components["pxOsd"].libs = ['usd_pxOsd']
        # geomUtil
        self.cpp_info.components["geomUtil"].requires = ['arch', 'gf', 'tf', 'vt', 'pxOsd']
        self.cpp_info.components["geomUtil"].libs = ['usd_geomUtil']
        # glf
        self.cpp_info.components["glf"].requires = ['ar', 'arch', 'garch', 'gf', 'hf', 'hio', 'plug', 'tf', 'trace', 'sdf'] + self.boost_python_libs
        self.cpp_info.components["glf"].libs = ['usd_glf']
        # hgi
        self.cpp_info.components["hgi"].requires = ['gf', 'plug', 'tf', 'hio']
        self.cpp_info.components["hgi"].libs = ['usd_hgi']
        # hgiGL
        self.cpp_info.components["hgiGL"].requires = ['arch', 'garch', 'hgi', 'tf', 'trace']
        self.cpp_info.components["hgiGL"].libs = ['usd_hgiGL']
        # hgiInterop
        self.cpp_info.components["hgiInterop"].requires = ['gf', 'tf', 'hgi', 'vt', 'garch']
        self.cpp_info.components["hgiInterop"].libs = ['usd_hgiInterop']
        # hd
        self.cpp_info.components["hd"].requires = ['plug', 'tf', 'trace', 'vt', 'work', 'sdf', 'cameraUtil', 'hf', 'pxOsd', 'sdr'] + self.tbb_libs
        self.cpp_info.components["hd"].libs = ['usd_hd']
        # hdar
        self.cpp_info.components["hdar"].requires = ['hd', 'ar']
        self.cpp_info.components["hdar"].libs = ['usd_hdar']
        # hdGp
        self.cpp_info.components["hdGp"].requires = ['hd', 'hf'] + self.tbb_libs
        self.cpp_info.components["hdGp"].libs = ['usd_hdGp']
        # hdsi
        self.cpp_info.components["hdsi"].requires = ['plug', 'tf', 'trace', 'vt', 'work', 'sdf', 'cameraUtil', 'geomUtil', 'hf', 'hd', 'pxOsd', 'usdGeom']
        self.cpp_info.components["hdsi"].libs = ['usd_hdsi']
        # hdMtlx
        if self.options.materialx:
            self.cpp_info.components["hdMtlx"].requires = ['gf', 'hd', 'sdf', 'sdr', 'tf', 'trace', 'usdMtlx', 'vt'] + ['materialx::MaterialXCore', 'materialx::MaterialXFormat']
            self.cpp_info.components["hdMtlx"].libs = ['usd_hdMtlx']
        else:
            self.cpp_info.components["hdMtlx"].requires = []
            self.cpp_info.components["hdMtlx"].libs = []
        # hdSt
        self.cpp_info.components["hdSt"].requires = ['hio', 'garch', 'glf', 'hd', 'hdsi', 'hgiGL', 'hgiInterop', 'sdr', 'tf', 'trace', 'hdMtlx', 'opensubdiv::osdcpu', 'opensubdiv::osdgpu']
        if self.options.materialx:
            self.cpp_info.components["hdSt"].requires += ['materialx::MaterialXGenShader', 'materialx::MaterialXRender', 'materialx::MaterialXCore', 'materialx::MaterialXFormat', 'materialx::MaterialXGenGlsl', 'materialx::MaterialXGenMsl']
        self.cpp_info.components["hdSt"].libs = ['usd_hdSt']
        # hdx
        self.cpp_info.components["hdx"].requires = ['plug', 'tf', 'vt', 'gf', 'work', 'garch', 'glf', 'pxOsd', 'hd', 'hdSt', 'hgi', 'hgiInterop', 'cameraUtil', 'sdf']
        self.cpp_info.components["hdx"].libs = ['usd_hdx']
        # usdImaging
        self.cpp_info.components["usdImaging"].requires = ['gf', 'tf', 'plug', 'trace', 'vt', 'work', 'geomUtil', 'hd', 'hdar', 'hio', 'pxOsd', 'sdf', 'usd', 'usdGeom', 'usdLux', 'usdRender', 'usdShade', 'usdVol', 'ar'] + self.tbb_libs
        self.cpp_info.components["usdImaging"].libs = ['usd_usdImaging']
        # usdImagingGL
        self.cpp_info.components["usdImagingGL"].requires = ['gf', 'tf', 'plug', 'trace', 'vt', 'work', 'hio', 'garch', 'glf', 'hd', 'hdsi', 'hdx', 'pxOsd', 'sdf', 'sdr', 'usd', 'usdGeom', 'usdHydra', 'usdShade', 'usdImaging', 'ar'] + self.boost_python_libs + self.tbb_libs
        self.cpp_info.components["usdImagingGL"].libs = ['usd_usdImagingGL']
        # usdProcImaging
        self.cpp_info.components["usdProcImaging"].requires = ['usdImaging', 'usdProc']
        self.cpp_info.components["usdProcImaging"].libs = ['usd_usdProcImaging']
        # usdRiPxrImaging
        self.cpp_info.components["usdRiPxrImaging"].requires = ['gf', 'tf', 'plug', 'trace', 'vt', 'work', 'hd', 'pxOsd', 'sdf', 'usd', 'usdGeom', 'usdLux', 'usdShade', 'usdImaging', 'usdVol', 'ar'] + self.tbb_libs
        self.cpp_info.components["usdRiPxrImaging"].libs = ['usd_usdRiPxrImaging']
        # usdSkelImaging
        self.cpp_info.components["usdSkelImaging"].requires = ['hio', 'hd', 'usdImaging', 'usdSkel']
        self.cpp_info.components["usdSkelImaging"].libs = ['usd_usdSkelImaging']
        # usdVolImaging
        self.cpp_info.components["usdVolImaging"].requires = ['usdImaging']
        self.cpp_info.components["usdVolImaging"].libs = ['usd_usdVolImaging']
        # usdAppUtils
        self.cpp_info.components["usdAppUtils"].requires = ['garch', 'gf', 'hio', 'sdf', 'tf', 'usd', 'usdGeom', 'usdImagingGL'] + self.boost_python_libs
        self.cpp_info.components["usdAppUtils"].libs = ['usd_usdAppUtils']
