#!/usr/bin/env python

import os, glob, sys, fnmatch, argparse, ctypes, inspect

MY_DIR = os.path.dirname(os.path.abspath(inspect.getframeinfo(inspect.currentframe())[0]))
HELPER_DIR = os.path.abspath(os.path.join(MY_DIR, '..', 'helpers'))
sys.path.append(HELPER_DIR)

from dhlog import *
from dhutil import Util

fn_hash_murmur32 = None

def search_hash_insource(src_filepath):
    try:
        f = open(src_filepath, 'r')
    except IOError as e:
        LogCon.warn('Warning: could not open source file: %s' % src_filepath)
    else:
        pos = 0
        end_pos = -1
        key = 'SHADER_NAME('
        ret = []
        src = f.read()
        f.close()
        while pos != -1:
            pos = src.find(key, pos)
            if pos != -1:
                pos += len(key)
                end_pos = src.find(')', pos)
                ret.append(src[pos:end_pos])
        return ret

def make_hashdefs_code(hash_defs, hash_seed):
    code = ''
    global fn_hash_murmur32
    for hash_def in hash_defs:
        defname = 'GFX_SHADERNAME_' + hash_def
        defname_c = ctypes.c_char_p(hash_def.encode('ascii', 'ignore'))
        hash_value = fn_hash_murmur32(defname_c, ctypes.c_uint(len(hash_def)), 
            ctypes.c_uint(hash_seed))
        codeline = '#define {0} {1} /* {2} */'.format(defname, hash_value, hash_def)
        code += codeline + '\n'
    return code

def write_code_tofile(header_path, code):
    header_comment = """
/***********************************************************************************
 * Copyright (c) 2014, Sepehr Taghdisian
 * All rights reserved.
 * 
 * Redistribution and use in source and binary forms, with or without modification, 
 * are permitted provided that the following conditions are met:
 *
 * - Redistributions of source code must retain the above copyright notice, 
 *   this list of conditions and the following disclaimer.
 * - Redistributions in binary form must reproduce the above copyright notice,
 *   this list of conditions and the following disclaimer in the documentation 
 *   and/or other materials provided with the distribution.
 *
 ***********************************************************************************/
 
  /**
  * Notice: This file is automatically generated with 'darkhammer/pytools/make-shvars' tool
  */\n\n"""
    try:
        f = open(header_path, 'w')
        f.write(header_comment)
        f.write(code)
        f.close()
    except IOError as e:
        LogCon.fatal('could not write to header: %s' % e.filename)
    else:
        LogCon.msgline('Hash data written to header: %s' % header_path, TERM_GREEN)

def main():
    parser = argparse.ArgumentParser(description='Make shader vars pre-hashed names from source')
    parser.add_argument('directory', nargs=1)
    parser.add_argument('-s', '--seed', action='store', default='98424', 
        help='hasher seed value (optional)')
    parser.add_argument('-o', '--output', action='store', default='gfx-shader-hashes.h', 
        help='output header file to save, file will be saved relative to directory argument (optional)')
    parser.add_argument('-l', '--hashlib', help='library file containing hash functions (dhcore)')
    parser.add_argument('-v', '--verbose', action='store_true')

    options = parser.parse_args(sys.argv[1:])
    if options.hashlib == None:
        LogCon.fatal('must provide a valid hash library (--hashlib argument)')
        sys.exit(-1)

    # load hash library and initialize hash function
    hashlib = os.path.abspath(options.hashlib)
    if not os.path.isfile(hashlib):
        LogCon.fatal('hash library not found: %s' % hashlib)
        sys.exit(-1)

    global fn_hash_murmur32

    LogCon.msgline('loading hash library: %s' % hashlib)
    try:
        lib_dhcore = ctypes.cdll.LoadLibrary(hashlib)
    
        fn_hash_murmur32 = lib_dhcore.hash_murmur32
        fn_hash_murmur32.restype = ctypes.c_uint
        fn_hash_murmur32.argtypes = [ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint]
    except:
        LogCon.fatal('hash library is invalid (not dhcore): %s' % hashlib)
        sys.exit(-1)


    # we have the function, get all source files
    indir = os.path.abspath(options.directory[0])
    if not os.path.isdir(indir):
        LogCon.fatal('invalid input directory: %s' % indir)
        sys.exit(-1)

    LogCon.msgline('parsing source files (c/cpp) in directory: %s' % indir)
    exts = ('*.cpp', '*.c')
    src_files = []
    src_files.extend(Util.glob_recursive(indir, exts))

    # for each source, parse SHADER_NAME and save hash_defs
    hash_defs = set('')
    lindir = len(indir)
    for f in src_files:
        if options.verbose:     LogCon.msgline(f[lindir+1:], TERM_GREY)
        hash_defs |= set(search_hash_insource(f))

    if options.verbose:
        LogCon.msgline('total %d unique SHADER_NAMEs found' % len(hash_defs))        

    # hash them and put them in the header
    outfile = os.path.abspath(os.path.join(indir, options.output))
    LogCon.msgline('saving to %s' % outfile)

    if len(hash_defs) > 0:
        code = make_hashdefs_code(hash_defs, int(options.seed))
        write_code_tofile(outfile, code)
    else:
        LogCon.warn('No SHADER_NAME macros found, so no output file generated')

main()

