import os
from pathlib import Path
from conan import ConanFile
from conan.tools.cmake import CMakeToolchain, CMakeDeps, CMake, cmake_layout
from conan.tools.files import get, copy

required_conan_version = ">=2.4.1"

class OpenUSD(ConanFile):
    name = "openusd"
    version = "system"
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
        'python_support': [True, False],
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

        'python_support': True,

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

        # ffmpeg->pulseaudio/14.2->gettext/0.21->build failures with some compilers
        # re-enable this after future update to oiio deps
        "openimageio/*:with_ffmpeg": False,
    }

    def requirements(self):
        if self.settings.os == 'Linux' and self.options.imaging:
            # self.requires('xorg/system')
            self.requires('opengl/system')

    def source(self):
        pass

    def generate(self):
        pass

    def build(self):
        pass

    def package(self):
        pass

    _usdfiles = None
    def _find_usdlib(self, name):
        libdir = Path(os.environ['OPENUSD_PATH'])/'lib'
        lib64dir = Path(os.environ['OPENUSD_PATH'])/'lib64'

        if not self._usdfiles:
            self._usdfiles = {
                'lib': os.listdir(libdir),
                'lib64': os.listdir(lib64dir),
            }
        
        match = []
        for file in self._usdfiles['lib']:
            if name in file and file.endswith('.so'):
                match.append((libdir/file).stem.split('lib')[-1])

        for file in self._usdfiles['lib64']:
            if name in file and file.endswith('.so'):
                match.append((lib64dir/file).stem.split('lib')[-1])
        return match

    def get_tbb_libs(self):
        return ['tbb'] # TODO: figure this out

    def package_info(self):
        assert 'OPENUSD_PATH' in os.environ, "Missing environment variable 'OPENUSD_PATH'"

        #-------------------------------------------------------------------------------------------
        # Dep lib names used by _auto_info
        self.onetbb_libs = self.get_tbb_libs()
        self.opensubdiv_libs = self._find_usdlib('libosdCPU') + self._find_usdlib('libosdGPU')
        self.boost_python_libs = self._find_usdlib('boost_python')

        self.ptex_libs = [] # ['ptex::ptex'] if self.options.ptex else []
        self.draco_libs = self._find_usdlib('libdraco')
        self.ocio_libs = self._find_usdlib('OpenColorIO')
        self.openvdb_libs = [] # ['openvdb::openvdb']  if self.options.openvdb else []
        self.alembic_libs = self._find_usdlib('Alembic')
        self.oiio_libs = self._find_usdlib('OpenImageIO')
        self.materialx_libs = self._find_usdlib('libMaterialX')
        self.embree_libs = self._find_usdlib('libembree')
        self.imath_libs = self._find_usdlib('Imath')

        # TODO...
        #-------------------------------------------------------------------------------------------
        self._auto_info()

        p_pkg = Path(os.environ['OPENUSD_PATH'])
        self.buildenv_info.prepend_path('PATH', str(p_pkg/'bin'))
        self.buildenv_info.prepend_path('PYTHONPATH', str(p_pkg/'lib'/'python'))
        self.runenv_info.prepend_path('PATH', str(p_pkg/'bin'))
        self.runenv_info.prepend_path('PYTHONPATH', str(p_pkg/'lib'/'python'))

        #-------------------------------------------------------------------------------------------
        # PLUGINS These are not found by depproc.py and don't expose any libs, but must be declared
        # as components anyways because conan may complain about unused dependencies

        if self.options.embree:
            self.cpp_info.components["hdEmbree"].requires = ['plug', 'tf', 'vt', 'gf', 'work', 'hf', 'hd', 'hdx']
            self.cpp_info.components["hdEmbree"].libs = self.onetbb_libs + self.embree_libs

        if self.options.draco:
            self.cpp_info.components["usdDraco"].requires = ['tf', 'gf', 'sdf', 'usd', 'usdGeom']
            self.cpp_info.components["usdDraco"].libs = self.draco_libs
        
        if self.options.alembic:
            self.cpp_info.components["usdAbc"].requires = ['tf', 'work', 'sdf', 'usd', 'usdGeom']
            self.cpp_info.components["usdAbc"].libs = self.alembic_libs + self.imath_libs
        
        if self.options.openvdb:
            self.cpp_info.components["hioOpenVDB"].requires = ['ar', 'gf', 'hio', 'tf', 'usd']
            self.cpp_info.components["hioOpenVDB"].libs = self.openvdb_libs + self.imath_libs
        
        if self.options.openimageio:
            self.cpp_info.components["hioOiio"].requires = ['ar', 'arch', 'gf', 'hio', 'tf']
            self.cpp_info.components["hioOiio"].libs = self.oiio_libs + self.imath_libs
        
        self.cpp_info.components["hdx"].libs.extend(self.ocio_libs)
        self.cpp_info.components["hdSt"].libs.extend(self.ptex_libs)
        #-------------------------------------------------------------------------------------------

        if self.settings.os == 'Linux':
            self.cpp_info.components["arch"].system_libs = ['m', 'dl']
            self.cpp_info.components["garch"].requires.append('opengl::opengl')
            self.cpp_info.components["glf"].requires.append('opengl::opengl') 

        p_lib = p_pkg/'lib'
        p_lib64 = p_pkg/'lib64'

        for comp in self.cpp_info.components:
            comp = self.cpp_info.components[comp]
            comp.includedirs = [str(p_pkg/'include')]
            comp.libdirs = [str(p_lib), str(p_lib64)]
            comp.libs = [lib for lib in comp.libs if (p_lib/('lib' + lib + '.so')).exists()]
    

    # this method was automatically generated with "depproc.py" and should not be modified directly
    def _auto_info(self):
        # boost
        # skipped
        # python
        self.cpp_info.components["python"].requires = [] #+ self.boost_python_libs
        self.cpp_info.components["python"].libs = ['usd_python'] + self.boost_python_libs
        # arch
        self.cpp_info.components["arch"].requires = []
        self.cpp_info.components["arch"].libs = ['usd_arch']
        # tf
        self.cpp_info.components["tf"].requires = ['arch', 'python']
        self.cpp_info.components["tf"].libs = ['usd_tf']
        self.cpp_info.components["tf"].system_libs = self.onetbb_libs
        # gf
        self.cpp_info.components["gf"].requires = ['arch', 'tf', 'python']
        self.cpp_info.components["gf"].libs = ['usd_gf']
        # pegtl
        self.cpp_info.components["pegtl"].requires = ['arch']
        self.cpp_info.components["pegtl"].libs = ['usd_pegtl']
        # js
        self.cpp_info.components["js"].requires = ['tf']
        self.cpp_info.components["js"].libs = ['usd_js']
        # trace
        self.cpp_info.components["trace"].requires = ['arch', 'js', 'tf']
        self.cpp_info.components["trace"].libs = ['usd_trace']
        self.cpp_info.components["trace"].system_libs = self.onetbb_libs
        # work
        self.cpp_info.components["work"].requires = ['tf', 'trace']
        self.cpp_info.components["work"].libs = ['usd_work']
        self.cpp_info.components["work"].system_libs = self.onetbb_libs
        # plug
        self.cpp_info.components["plug"].requires = ['arch', 'tf', 'js', 'trace', 'work']
        self.cpp_info.components["plug"].libs = ['usd_plug']
        self.cpp_info.components["plug"].system_libs = self.onetbb_libs
        # vt
        self.cpp_info.components["vt"].requires = ['arch', 'tf', 'gf', 'trace', 'python']
        self.cpp_info.components["vt"].libs = ['usd_vt']
        self.cpp_info.components["vt"].system_libs = self.onetbb_libs
        # ts
        self.cpp_info.components["ts"].requires = ['vt', 'gf', 'tf']
        self.cpp_info.components["ts"].libs = ['usd_ts']
        # ar
        self.cpp_info.components["ar"].requires = ['arch', 'js', 'tf', 'plug', 'vt', 'python']
        self.cpp_info.components["ar"].libs = ['usd_ar']
        self.cpp_info.components["ar"].system_libs = self.onetbb_libs
        # kind
        self.cpp_info.components["kind"].requires = ['tf', 'plug']
        self.cpp_info.components["kind"].libs = ['usd_kind']
        # sdf
        self.cpp_info.components["sdf"].requires = ['arch', 'tf', 'gf', 'pegtl', 'trace', 'ts', 'vt', 'work', 'ar', 'python']
        self.cpp_info.components["sdf"].libs = ['usd_sdf']
        self.cpp_info.components["sdf"].system_libs = self.onetbb_libs
        # ndr
        self.cpp_info.components["ndr"].requires = ['tf', 'plug', 'vt', 'work', 'ar', 'sdf']
        self.cpp_info.components["ndr"].libs = ['usd_ndr']
        # sdr
        self.cpp_info.components["sdr"].requires = ['tf', 'vt', 'ar', 'ndr', 'sdf']
        self.cpp_info.components["sdr"].libs = ['usd_sdr']
        # pcp
        self.cpp_info.components["pcp"].requires = ['tf', 'trace', 'vt', 'sdf', 'work', 'ar', 'python']
        self.cpp_info.components["pcp"].libs = ['usd_pcp']
        self.cpp_info.components["pcp"].system_libs = self.onetbb_libs
        # usd
        self.cpp_info.components["usd"].requires = ['arch', 'kind', 'pcp', 'sdf', 'ar', 'plug', 'tf', 'trace', 'ts', 'vt', 'work', 'python']
        self.cpp_info.components["usd"].libs = ['usd_usd']
        self.cpp_info.components["usd"].system_libs = self.onetbb_libs
        # usdGeom
        self.cpp_info.components["usdGeom"].requires = ['js', 'tf', 'plug', 'vt', 'sdf', 'trace', 'usd', 'work']
        self.cpp_info.components["usdGeom"].libs = ['usd_usdGeom']
        self.cpp_info.components["usdGeom"].system_libs = self.onetbb_libs
        # usdVol
        self.cpp_info.components["usdVol"].requires = ['tf', 'usd']
        self.cpp_info.components["usdVol"].libs = ['usd_usdVol']
        # usdMedia
        self.cpp_info.components["usdMedia"].requires = ['tf', 'vt', 'sdf', 'usd']
        self.cpp_info.components["usdMedia"].libs = ['usd_usdMedia']
        # usdShade
        self.cpp_info.components["usdShade"].requires = ['tf', 'vt', 'js', 'sdf', 'ndr', 'sdr', 'usd']
        self.cpp_info.components["usdShade"].libs = ['usd_usdShade']
        self.cpp_info.components["usdShade"].system_libs = self.onetbb_libs
        # usdLux
        self.cpp_info.components["usdLux"].requires = ['tf', 'vt', 'ndr', 'sdf', 'usd', 'usdShade']
        self.cpp_info.components["usdLux"].libs = ['usd_usdLux']
        # usdProc
        self.cpp_info.components["usdProc"].requires = ['tf', 'usd']
        self.cpp_info.components["usdProc"].libs = ['usd_usdProc']
        # usdRender
        self.cpp_info.components["usdRender"].requires = ['gf', 'tf', 'usd', 'usdShade']
        self.cpp_info.components["usdRender"].libs = ['usd_usdRender']
        # usdHydra
        self.cpp_info.components["usdHydra"].requires = ['tf', 'usd', 'usdShade']
        self.cpp_info.components["usdHydra"].libs = ['usd_usdHydra']
        # usdRi
        self.cpp_info.components["usdRi"].requires = ['tf', 'vt', 'sdf', 'usd', 'usdShade']
        self.cpp_info.components["usdRi"].libs = ['usd_usdRi']
        # usdSemantics
        self.cpp_info.components["usdSemantics"].requires = ['tf', 'vt', 'usd']
        self.cpp_info.components["usdSemantics"].libs = ['usd_usdSemantics']
        # usdSkel
        self.cpp_info.components["usdSkel"].requires = ['arch', 'gf', 'tf', 'trace', 'vt', 'work', 'sdf', 'usd']
        self.cpp_info.components["usdSkel"].libs = ['usd_usdSkel']
        self.cpp_info.components["usdSkel"].system_libs = self.onetbb_libs
        # usdUI
        self.cpp_info.components["usdUI"].requires = ['tf', 'vt', 'sdf', 'usd']
        self.cpp_info.components["usdUI"].libs = ['usd_usdUI']
        # usdUtils
        self.cpp_info.components["usdUtils"].requires = ['arch', 'tf', 'gf', 'sdf', 'usd', 'usdShade']
        self.cpp_info.components["usdUtils"].libs = ['usd_usdUtils']
        self.cpp_info.components["usdUtils"].system_libs = self.onetbb_libs
        # usdPhysics
        self.cpp_info.components["usdPhysics"].requires = ['tf', 'plug', 'vt', 'sdf', 'trace', 'usd', 'usdShade', 'work']
        self.cpp_info.components["usdPhysics"].libs = ['usd_usdPhysics']
        self.cpp_info.components["usdPhysics"].system_libs = self.onetbb_libs
        # usdValidation
        self.cpp_info.components["usdValidation"].requires = ['sdf', 'plug', 'tf', 'gf', 'usd', 'work']
        self.cpp_info.components["usdValidation"].libs = ['usd_usdValidation']
        self.cpp_info.components["usdValidation"].system_libs = self.onetbb_libs
        # usdGeomValidators
        self.cpp_info.components["usdGeomValidators"].requires = ['tf', 'plug', 'sdf', 'usd', 'usdValidation']
        self.cpp_info.components["usdGeomValidators"].libs = ['usd_usdGeomValidators']
        # usdShadeValidators
        self.cpp_info.components["usdShadeValidators"].requires = ['tf', 'plug', 'sdf', 'usd', 'ndr', 'sdr', 'usdShade', 'usdValidation']
        self.cpp_info.components["usdShadeValidators"].libs = ['usd_usdShadeValidators']
        # usdSkelValidators
        self.cpp_info.components["usdSkelValidators"].requires = ['tf', 'plug', 'sdf', 'usd', 'usdSkel', 'usdValidation']
        self.cpp_info.components["usdSkelValidators"].libs = ['usd_usdSkelValidators']
        # usdUtilsValidators
        self.cpp_info.components["usdUtilsValidators"].requires = ['tf', 'plug', 'sdf', 'usd', 'usdUtils', 'usdValidation']
        self.cpp_info.components["usdUtilsValidators"].libs = ['usd_usdUtilsValidators']
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
        self.cpp_info.components["pxOsd"].requires = ['tf', 'gf', 'vt']
        self.cpp_info.components["pxOsd"].libs = ['usd_pxOsd'] + self.opensubdiv_libs
        # geomUtil
        self.cpp_info.components["geomUtil"].requires = ['arch', 'gf', 'tf', 'vt', 'pxOsd']
        self.cpp_info.components["geomUtil"].libs = ['usd_geomUtil']
        # glf
        self.cpp_info.components["glf"].requires = ['ar', 'arch', 'garch', 'gf', 'hf', 'hio', 'plug', 'tf', 'trace', 'sdf']
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
        self.cpp_info.components["hd"].requires = ['plug', 'tf', 'trace', 'vt', 'work', 'sdf', 'hf', 'pxOsd', 'sdr']
        self.cpp_info.components["hd"].libs = ['usd_hd']
        self.cpp_info.components["hd"].system_libs = self.onetbb_libs
        # hdar
        self.cpp_info.components["hdar"].requires = ['hd', 'ar']
        self.cpp_info.components["hdar"].libs = ['usd_hdar']
        # hdGp
        self.cpp_info.components["hdGp"].requires = ['hd', 'hf']
        self.cpp_info.components["hdGp"].libs = ['usd_hdGp']
        self.cpp_info.components["hdGp"].system_libs = self.onetbb_libs
        # hdsi
        self.cpp_info.components["hdsi"].requires = ['plug', 'tf', 'trace', 'vt', 'work', 'sdf', 'hf', 'hd', 'pxOsd']
        self.cpp_info.components["hdsi"].libs = ['usd_hdsi']
        # hdSt
        self.cpp_info.components["hdSt"].requires = ['hio', 'garch', 'glf', 'hd', 'hdsi', 'hgiGL', 'hgiInterop', 'sdr', 'tf', 'trace', 'hdMtlx']
        self.cpp_info.components["hdSt"].libs = ['usd_hdSt'] + self.opensubdiv_libs + self.materialx_libs
        self.cpp_info.components["hdSt"].system_libs = self.onetbb_libs
        # hdx
        self.cpp_info.components["hdx"].requires = ['plug', 'tf', 'vt', 'gf', 'work', 'garch', 'glf', 'pxOsd', 'hd', 'hdSt', 'hgi', 'hgiInterop', 'sdf']
        self.cpp_info.components["hdx"].libs = ['usd_hdx']
        # usdImaging
        self.cpp_info.components["usdImaging"].requires = ['gf', 'tf', 'plug', 'trace', 'vt', 'work', 'hd', 'hdar', 'hio', 'pxOsd', 'sdf', 'usd', 'usdLux', 'usdRender', 'usdShade', 'usdVol', 'ar']
        self.cpp_info.components["usdImaging"].libs = ['usd_usdImaging']
        self.cpp_info.components["usdImaging"].system_libs = self.onetbb_libs
        # usdImagingGL
        self.cpp_info.components["usdImagingGL"].requires = ['gf', 'tf', 'plug', 'trace', 'vt', 'work', 'hio', 'garch', 'glf', 'hd', 'hdsi', 'hdx', 'pxOsd', 'sdf', 'sdr', 'usd', 'usdHydra', 'usdShade', 'ar']
        self.cpp_info.components["usdImagingGL"].libs = ['usd_usdImagingGL']
        self.cpp_info.components["usdImagingGL"].system_libs = self.onetbb_libs
        # usdProcImaging
        self.cpp_info.components["usdProcImaging"].requires = ['usdProc']
        self.cpp_info.components["usdProcImaging"].libs = ['usd_usdProcImaging']
        # usdRiPxrImaging
        self.cpp_info.components["usdRiPxrImaging"].requires = ['gf', 'tf', 'plug', 'trace', 'vt', 'work', 'hd', 'pxOsd', 'sdf', 'usd', 'usdLux', 'usdShade', 'usdVol', 'ar']
        self.cpp_info.components["usdRiPxrImaging"].libs = ['usd_usdRiPxrImaging']
        self.cpp_info.components["usdRiPxrImaging"].system_libs = self.onetbb_libs
        # usdSkelImaging
        self.cpp_info.components["usdSkelImaging"].requires = ['hio', 'hd', 'usdSkel']
        self.cpp_info.components["usdSkelImaging"].libs = ['usd_usdSkelImaging']
        # usdVolImaging
        self.cpp_info.components["usdVolImaging"].requires = []
        self.cpp_info.components["usdVolImaging"].libs = ['usd_usdVolImaging']
        # usdAppUtils
        self.cpp_info.components["usdAppUtils"].requires = ['garch', 'gf', 'hio', 'sdf', 'tf', 'usd']
        self.cpp_info.components["usdAppUtils"].libs = ['usd_usdAppUtils']
        # usdMtlx
        if self.options.materialx:
            self.cpp_info.components["usdMtlx"].requires = ['arch', 'gf', 'ndr', 'sdf', 'sdr', 'tf', 'vt', 'usd', 'usdShade', 'usdUI', 'usdUtils']
            self.cpp_info.components["usdMtlx"].libs = ['usd_usdMtlx'] + self.materialx_libs
        else:
            self.cpp_info.components["usdMtlx"].requires = []
            self.cpp_info.components["usdMtlx"].libs = []
        # hdMtlx
        if self.options.materialx:
            self.cpp_info.components["hdMtlx"].requires = ['gf', 'hd', 'sdf', 'sdr', 'tf', 'trace', 'usdMtlx', 'vt']
            self.cpp_info.components["hdMtlx"].libs = ['usd_hdMtlx'] + self.materialx_libs
        else:
            self.cpp_info.components["hdMtlx"].requires = []
            self.cpp_info.components["hdMtlx"].libs = []
