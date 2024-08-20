#! /usr/bin/env python

"""
	This is a helper script to scrape all of the components and their dependencies, and is used to
	generate the `_auto_info` method in conanfile.py. It works by parsing `pxrTargets.cmake`
	build artifact from a standard openusd build. 

	Example usage:

	```
		./depproc.py /path/to/openusd/build
	```

	This should be re-run when there's a new openusd version and compared with the existing.
"""

import sys, json

tab = ' ' * 4

# These are the C lib components of some cli programs with python entrypoints. They should be used
# via their cli and not linked directly as libraries, so they're not exposed as conan components.
skip_libs = [
	'usdBakeMtlx',
	'usdviewq',
]

known_libs = [
	'usd_arch',
	'usd_tf',
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
]

def replace_known_reqs(reqstr):
	if reqstr == 'dl': return None
	if '/' in reqstr: return None
	
	# TODO: is this ok?
	if 'Python3::Python' in reqstr: return None

	if reqstr == 'OpenColorIO::OpenColorIO': return 'opencolorio::opencolorio'
	if reqstr == 'TBB::tbb': return 'onetbb::libtbb'
	if reqstr == 'TBB::tbbmalloc': return 'onetbb::tbbmalloc'
	if reqstr == 'TBB::tbbmalloc_proxy': return 'onetbb::tbbmalloc_proxy'
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
				out[cur_target]['needs_tbb'] = False
				out[cur_target]['needs_boost_python'] = False
				out[cur_target]['materialx_libs'] = []
				for lib in items:
					if 'libboost_python' in lib.lower():
						out[cur_target]['needs_boost_python'] = True
					elif 'libtbb' in lib.lower():
						out[cur_target]['needs_tbb'] = True
					elif 'libosd' in lib.lower():
						if 'libosdCPU' in lib:
							out[cur_target]['link_libs'].append('opensubdiv::osdcpu')
						elif 'libosdGPU' in lib:
							out[cur_target]['link_libs'].append('opensubdiv::osdgpu')
						else:
							assert False, f'Unrecognized libosd library: {lib}'
					elif 'materialx' in lib.lower():
						out[cur_target]['materialx_libs'].append(replace_known_reqs(lib))
					else:
						out[cur_target]['link_libs'].append(replace_known_reqs(lib))
			
			if 'INTERFACE_SYSTEM_INCLUDE_DIRECTORIES' in l:
				sp = l.replace('"','').split('INTERFACE_SYSTEM_INCLUDE_DIRECTORIES ')[1]
				items = [s.replace('\n', '').replace('${_IMPORT_PREFIX}/', '') for s in sp.split(';')]
				out[cur_target]['sys_include'] = items
	return out


def get_libs(name, all_targets):
	if '::' in name: return []
	return [f'usd_{name}']


def build_component(name, all_targets):
	out = []
	target = all_targets[name]
	inc = target.get('include', []) + target.get('sys_include', [])

	reqs = []
	libs = get_libs(name, all_targets)
	for req in target['link_libs']:
		if req:
			reqs.append(req)

	for l in libs:
		assert l in known_libs, f"Uknown lib: {l}"

	reqstr = str(reqs)
	if target['needs_boost_python']:
		reqstr += ' + self.boost_python_libs'
	if target['needs_tbb']:
		reqstr += ' + self.tbb_libs'

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