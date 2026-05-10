#! /usr/bin/env python
import sys, json

tab = ' '*4

# these are the C lib components of some cli programs with python entrypoints
# they should be used via their cli and not linked directly as libraries
skip_libs = [
	'usdBakeMtlx',
	'usdviewq',
]

known_libs = [
	'usd_arch',
	'usd_tf',
	'usd_ts',
	'usd_gf',
	'usd_js',
	'usd_trace',
	'usd_work',
	'usd_plug',
	'usd_vt',
	'usd_ar',
	'usd_kind',
	'usd_sdf',
	'usd_ndr',
	'usd_sdr',
	'usd_pcp',
	'usd_usd',
	'usd_python',
	'usd_usdGeom',
	'usd_usdVol',
	'usd_usdMedia',
	'usd_usdShade',
	'usd_usdLux',
	'usd_usdProc',
	'usd_usdRender',
	'usd_usdHydra',
	'usd_usdRi',
	'usd_usdSkel',
	'usd_usdUI',
	'usd_usdUtils',
	'usd_usdPhysics',
	'usd_usdMtlx',
	'usd_garch',
	'usd_hf',
	'usd_hio',
	'usd_cameraUtil',
	'usd_pxOsd',
	'usd_geomUtil',
	'usd_glf',
	'usd_hgi',
	'usd_hgiGL',
	'usd_hgiInterop',
	'usd_hd',
	'usd_hdar',
	'usd_hdGp',
	'usd_hdsi',
	'usd_hdMtlx',
	'usd_hdSt',
	'usd_hdx',
	'usd_usdImaging',
	'usd_usdImagingGL',
	'usd_usdProcImaging',
	'usd_usdRiPxrImaging',
	'usd_usdSkelImaging',
	'usd_usdVolImaging',
	'usd_usdAppUtils',
	'usd_usdBakeMtlx',
	'usd_usdSemantics', # added in 24.11
	'usd_pegtl',
	'usd_usdValidation',
	'usd_usdGeomValidators',
	'usd_usdShadeValidators',
	'usd_usdSkelValidators',
	'usd_usdUtilsValidators',
]

def replace_known_reqs(reqstr):
	if 'm' in reqstr: return None
	if reqstr == 'dl': return None
	if '/' in reqstr: return None
	
	if 'Python3::Python' in reqstr: return None

	if 'OpenGL::GL' in reqstr: return None	

	if reqstr == 'OpenColorIO::OpenColorIO': return 'opencolorio::opencolorio'
	if reqstr.lower() == 'tbb::tbb': return 'onetbb::libtbb'
	if reqstr.lower() == 'tbb::tbbmalloc': return 'onetbb::tbbmalloc'
	if reqstr.lower() == 'tbb::tbbmalloc_proxy': return 'onetbb::tbbmalloc_proxy'
	if 'materialx' in reqstr.lower():
		if '::' in reqstr:
			reqstr = reqstr.split('::')[1]
		return f'materialx::{reqstr}'
	return reqstr


def get_targets(filename):
	out = {}
	with open(filename) as f:
		cur_target = None
		_skip = False
		while l := f.readline():
			if 'add_library(' in l:
				cur_target = l.split('add_library(')[1].split(' ')[0]

				if cur_target in skip_libs:
					_skip = True
					continue

				_skip = False

				out[cur_target] = {}

			if _skip:
				continue

			if 'INTERFACE_INCLUDE_DIRECTORIES' in l:
				sp = l.replace('"','').split('INTERFACE_INCLUDE_DIRECTORIES ')[1]
				items = [s.replace('\n', '').replace('${_IMPORT_PREFIX}/', '') for s in sp.split(';')]
				out[cur_target]['include'] = items

			if 'INTERFACE_LINK_LIBRARIES' in l:
				sp = l.replace('"','').split('INTERFACE_LINK_LIBRARIES ')[1]
				items = [s.replace('\n', '').replace('${_IMPORT_PREFIX}/', '') for s in sp.split(';')]
				out[cur_target]['link_libs'] = []
				
				# TODO: refactor this mess
				out[cur_target]['needs_boost_python'] = False
				out[cur_target]['needs_osd'] = False
				out[cur_target]['needs_tbb'] = False
				out[cur_target]['needs_openvdb'] = False
				out[cur_target]['needs_alembic'] = False
				out[cur_target]['needs_draco'] = False
				out[cur_target]['needs_ptex'] = False
				out[cur_target]['needs_ocio'] = False
				out[cur_target]['needs_oiio'] = False
				out[cur_target]['materialx_libs'] = []
				for lib in items:
					llib = lib.lower()
					if 'boost' in llib: # pretty sure 'boost' deps are only on boost python
						out[cur_target]['needs_boost_python'] = True
					elif 'tbb' in llib:
						out[cur_target]['needs_tbb'] = True
					elif 'openvdb' in llib:
						out[cur_target]['needs_openvdb'] = True
					elif 'alembic' in llib:
						out[cur_target]['needs_alembic'] = True
					elif 'draco' in llib:
						out[cur_target]['needs_draco'] = True
					elif 'ptex::' in llib:
						out[cur_target]['needs_needs_ptex'] = True
					elif 'opensubdiv' in llib:
						out[cur_target]['needs_osd'] = True
					elif 'opencolorio' in llib:
						out[cur_target]['needs_ocio'] = True
					elif 'openimageio' in llib:
						out[cur_target]['needs_oiio'] = True
					elif 'materialx' in llib:
						if k := replace_known_reqs(lib):
							out[cur_target]['materialx_libs'].append(k)
					else:
						if k := replace_known_reqs(lib):
							out[cur_target]['link_libs'].append(k)
			
			if 'INTERFACE_SYSTEM_INCLUDE_DIRECTORIES' in l:
				sp = l.replace('"','').split('INTERFACE_SYSTEM_INCLUDE_DIRECTORIES ')[1]
				items = [s.replace('\n', '').replace('${_IMPORT_PREFIX}/', '') for s in sp.split(';')]
				out[cur_target]['sys_include'] = items
	return out


def get_libs(name, all_targets):
	if '::' in name: return []
	if name in known_libs:
		return [name]
	else:
		return [f'usd_{name}']


def build_component(name, all_targets):
	out = []
	target = all_targets[name]
	inc = target.get('include', []) + target.get('sys_include', [])

	reqs = []
	libs = get_libs(name, all_targets)
	for req in target.get('link_libs', []):
		if req:
			reqs.append(req)

	for l in libs:
		assert l in known_libs, f"Unknown lib: {l}"

	reqstr = str(reqs)
	if target['needs_boost_python']:
		reqstr += ' + self.boost_python_libs'
	
	if target['needs_osd']:
		reqstr += ' + self.opensubdiv_libs'
	
	if target['needs_tbb']:
		reqstr += ' + self.onetbb_libs'
	
	if target['needs_draco']:
		reqstr += ' + self.draco_libs'
	
	if target['needs_ptex']:
		reqstr += ' + self.ptex_libs'

	if target['needs_ocio']:
		reqstr += ' + self.ocio_libs'
	
	if target['needs_oiio']:
		reqstr += ' + self.oiio_libs'
	
	if target['needs_openvdb']:
		reqstr += ' + self.openvdb_libs'
	
	if target['needs_alembic']:
		reqstr += ' + self.alembic_libs'

	if name in ['usdMtlx', 'hdMtlx']:
		# make sure to only include these components if the materialx option is true
		reqstr += ' + %s' % (target['materialx_libs'])
		out.append(f"if self.options.materialx:")
		out.append(f"{tab}self.cpp_info.components[\"{name}\"].requires = {reqstr}")
		out.append(f"{tab}self.cpp_info.components[\"{name}\"].libs = {libs}")
		out.append(f"else:")
		out.append(f"{tab}self.cpp_info.components[\"{name}\"].requires = []")
		out.append(f"{tab}self.cpp_info.components[\"{name}\"].libs = []")
	else:	
		out.append(f"self.cpp_info.components[\"{name}\"].requires = {reqstr}")
		if mxlibs := target['materialx_libs']:
			out.append(f"if self.options.materialx:")
			out.append(f"{tab}self.cpp_info.components[\"{name}\"].requires += {mxlibs}")
		out.append(f"self.cpp_info.components[\"{name}\"].libs = {libs}")
	return out


def print_usage():
	print(f"USAGE:\n\t{sys.argv[0]} </path/to/pxrTargets.cmake> [-v]\n")
	print("pxrTarget.cmake can be found in the 'cmake' install folder after performing a standard build and install.\n")
	print("On Linux, you can use this command to find it:\n\tfind /path/to/openusd -name \"pxrTargets.cmake\"")


if __name__ == '__main__':
	if not len(sys.argv) >= 2:
		print_usage()
		sys.exit(1)

	targets = get_targets(sys.argv[1])
	
	if len(sys.argv) == 3 and '-v' in sys.argv:
		print(json.dumps(targets, indent=2))

	print(f'{tab}def _auto_info(self):')
	for target in targets:
		print(f'{tab}{tab}#', target)
		try:
			print(f'{tab}{tab}' + f'\n{tab}{tab}'.join(build_component(target, targets)))
		except AssertionError as e:
			print(f'{tab}{tab}# skipped')
