import os
from pathlib import Path
from conan import ConanFile
from conan.tools.cmake import CMakeToolchain, CMakeDeps, CMake, cmake_layout
from conan.tools.files import copy, get

required_conan_version = ">=2.4.1"

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
        'draco': [True, False], # enable usdDraco plugin
        'alembic': [True, False], # enable usdAbc plugin
        'openvdb': [True, False],
        'safety_over_speed': [True, False], # trade performance for safety with malformed input files
    }
    default_options = {
        'shared': True,
        'fPIC': False,
        'usd': True,
        'imaging': True,
        'usdimaging': True,
        'tools': True,
        'opencolorio': True,
        'ptex': True,
        'openimageio': True,
        'draco': True,
        'alembic': True,
        'openvdb': True,

        'safety_over_speed': True,

        'materialx': True,
        'materialx/*:render': True,
        
        'onetbb/*:tbbmalloc': False,
        'onetbb/*:tbbproxy': False,

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

        needs_imath = False

        if self.options.ptex:
            self.do_requires('ptex')

        if self.options.draco:
            self.do_requires('draco')
        
        if self.options.alembic:
            self.do_requires('alembic')
            needs_imath = True

        if self.options.openvdb:
            self.do_requires('openvdb')
            needs_imath = True

        if self.options.embree:
            self.do_requires('embree3')

        if self.options.opencolorio:
            self.do_requires('opencolorio')

        if self.options.materialx:
            self.do_requires('materialx')

        if self.settings.os == 'Linux' and self.options.imaging:
            # self.requires('xorg/system')
            self.requires('opengl/system')
        
        if self.options.openimageio:
            self.do_requires('openimageio')
            needs_imath = True

        if needs_imath:
            self.do_requires('imath')

        # MISSING
        # self.requires('osl/1.10.9')

        # overrides
        for pkg in self.conan_data[self.version]['overrides']:
            self.requires(pkg, override = True)


    def source(self):
        get(self, **self.conan_data[self.version]["sources"], strip_root=True, destination=self.source_folder)


    def _patch_sources_cmake(self):
        # OpenUSD uses these cmake files to find third party libraries, but the goal is to provide
        # those libraries via conan, so we delete them and make sure to produce the correct cache
        # variables/target aliases that OpenUSD expects from these modules
        files_to_delete = [
            'FindTBB.cmake',
            'FindOpenSubdiv.cmake',
            'FindEmbree.cmake',
            'FindAlembic.cmake',
            'FindAnimX.cmake',
            'FindDraco.cmake',
            'FindJinja2.cmake',
            'FindOpenColorIO.cmake',
            'FindOpenEXR.cmake',
            'FindOpenImageIO.cmake',
            'FindOpenVDB.cmake',
            'FindOSL.cmake',
            'FindPTex.cmake',
            # 'FindPyOpenGL.cmake',
            # 'FindPySide.cmake',
            'FindRenderman.cmake',
        ]
        for file in files_to_delete:
            os.remove(Path(self.source_folder)/"cmake"/"modules"/file)


    def generate(self):
        tc = CMakeToolchain(self)
        dep = CMakeDeps(self)
        
        tc.variables['BUILD_SHARED_LIBS'] = self.options.shared

        # this helps OpenUSD build scripts find CMake targets from conan dependencies
        # (kind of like aliases for cmake target names)

        tc.variables['TBB_tbb_LIBRARY'] = self.dependencies["onetbb"].cpp_info.get_property('cmake_target_name')

        if self.options.ptex:
            tc.variables['PTEX_LIBRARY'] = self.dependencies["ptex"].cpp_info.get_property('cmake_target_name')

        if self.options.draco:
            tc.variables['DRACO_LIBRARY'] = self.dependencies["draco"].cpp_info.get_property('cmake_target_name')

        if self.options.openvdb:
            tc.variables['OPENVDB_LIBRARY'] = self.dependencies["openvdb"].cpp_info.get_property('cmake_target_name')

        if self.options.alembic:
            tc.variables['ALEMBIC_LIBRARIES'] = self.dependencies["alembic"].cpp_info.get_property('cmake_target_name')
            tc.variables['PXR_ENABLE_HDF5_SUPPORT'] = self.dependencies["alembic"].options.with_hdf5
            tc.variables['ALEMBIC_FOUND'] = True

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

        if self.options.openimageio:
            dep.set_property("opencolorio", "cmake_additional_variables_prefixes", ["OCIO"])

        if self.options.opencolorio:
            dep.set_property("openimageio", "cmake_additional_variables_prefixes", ["OIIO"])

        if self.options.materialx:
            # create aliases like 'materialx::MaterialXCore' => 'MaterialXCore'
            # materialx conan package produces the former, openusd expects the latter
            mtx = self.dependencies["materialx"]
            mtx_comps = {
                'MaterialXCore',
                'MaterialXFormat',
                'MaterialXGenGlsl',
                'MaterialXGenMdl',
                'MaterialXGenMsl',
                'MaterialXGenOsl',
                'MaterialXGenShader',
                'MaterialXRender',
                'MaterialXRenderGlsl',
                'MaterialXRenderHw',
                'MaterialXRenderOsl',
                'MaterialXRenderMsl'
            }
            for comp in mtx_comps:
                if comp in mtx.cpp_info.components.keys():
                    info = mtx.cpp_info.components[comp]
                    info.set_property('cmake_target_aliases', [comp])

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

                'PXR_PREFER_SAFETY_OVER_SPEED': self.options.safety_over_speed,

                'PXR_ENABLE_PYTHON_SUPPORT': True,
                'PXR_ENABLE_GL_SUPPORT': True,
                'PXR_ENABLE_VULKAN_SUPPORT': False, # for hgiVulkan, may need to patch `cmake/defaults/Packages.cmake`
                'PXR_ENABLE_OSL_SUPPORT': False, # currently, no OSL conan package exists
                'PXR_ENABLE_OPENVDB_SUPPORT': self.options.openvdb,

                'PXR_BUILD_EMBREE_PLUGIN': self.options.embree,
                'PXR_BUILD_PRMAN_PLUGIN': False,
                'PXR_BUILD_ALEMBIC_PLUGIN': self.options.alembic,
                'PXR_BUILD_DRACO_PLUGIN': self.options.draco,

                'PXR_BUILD_DOCUMENTATION': False,
                'PXR_BUILD_TESTS': False,
                'PXR_BUILD_EXAMPLES': False,
                'PXR_BUILD_TUTORIALS': False,
                
                'PXR_BUILD_IMAGING': self.options.imaging,
                'PXR_BUILD_USD_TOOLS': self.options.tools,
                'PXR_BUILD_USDVIEW': self.options.tools,
                
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
        self.tbb_libs = ['onetbb::onetbb']

        self._auto_info()

        p_pkg = Path(self.package_folder)
        self.buildenv_info.prepend_path('PATH', str(p_pkg/'bin'))
        self.buildenv_info.prepend_path('PYTHONPATH', str(p_pkg/'lib'/'python'))

        #-------------------------------------------------------------------------------------------
        # PLUGINS These are not found by depproc.py and don't expose any libs, but must be declared
        # as components anyways because conan may complain about unused dependencies

        if self.options.embree:
            self.cpp_info.components["hdEmbree"].requires = ['plug', 'tf', 'vt', 'gf', 'work', 'hf', 'hd', 'hdx', 'embree3::embree3'] + self.tbb_libs
            self.cpp_info.components["hdEmbree"].libs = []

        if self.options.draco:
            self.cpp_info.components["usdDraco"].requires = ['tf', 'gf', 'sdf', 'usd', 'usdGeom', 'draco::draco']
            self.cpp_info.components["usdDraco"].libs = []
        
        if self.options.alembic:
            self.cpp_info.components["usdAbc"].requires = ['tf', 'work', 'sdf', 'usd', 'usdGeom', 'alembic::alembic', 'imath::imath_lib', 'imath::imath_config']
            self.cpp_info.components["usdAbc"].libs = []
        
        if self.options.openvdb:
            self.cpp_info.components["hioOpenVDB"].requires = ['ar', 'gf', 'hio', 'tf', 'usd', 'imath::imath_lib', 'openvdb::openvdb']
            self.cpp_info.components["hioOpenVDB"].libs = []
        
        if self.options.openimageio:
            self.cpp_info.components["hioOiio"].requires = ['ar', 'arch', 'gf', 'hio', 'tf', 'openimageio::openimageio', 'imath::imath_lib']
            self.cpp_info.components["hioOiio"].libs = []
        
        if self.options.opencolorio:
            self.cpp_info.components["hdx"].requires.append('opencolorio::opencolorio')
        
        if self.options.ptex:
            self.cpp_info.components["hdSt"].requires.append('ptex::ptex')
        #-------------------------------------------------------------------------------------------

        if self.settings.os == 'Linux':
            self.cpp_info.components["arch"].system_libs = ['m', 'dl']
            self.cpp_info.components["garch"].requires.append('opengl::opengl')
            self.cpp_info.components["glf"].requires.append('opengl::opengl')
    

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
