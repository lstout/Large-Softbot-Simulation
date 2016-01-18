#!/bin/sh

rootDir=`pwd`
boost_root=/usr/include/boost
boost_stage=/usr/lib/
boost_lib_ext=dylib
boost_gxx=xgcc40
tinyXML_root=${rootDir}/tinyxmldll
JGTL_include=${rootDir}/JGTL/include
ode_root=${rootDir}/../libode




echo Building required packages
echo

# build TinyXML
if test -e ${tinyXML_root}/out/libtinyxmldll.${boost_lib_ext}
then
    echo TinyXML exists.  Skipping
    echo
else
    echo Building TinyXML
    cd ${rootDir}
    mkdir -p zlib/build/cygwin_debug
    mkdir -p zlib/build/cygwin_release
    cd zlib
    ccmake .
    make

    cd ..
    mkdir -p tinyxmldll/build/cygwin_debug
    mkdir -p tinyxmldll/build/cygwin_release
    cd tinyxmldll
    ccmake .
    make
    cd ${rootDir}

    echo Finished making TinyXML
    echo
fi

# build Boost
if test -e ${boost_stage}/libboost_filesystem.a &&
   test -e ${boost_stage}/libboost_system.a &&
   test -e ${boost_stage}/libboost_thread.so
#
#if test -e ${boost_stage}/libboost_thread-${boost_gxx}-mt.${boost_lib_ext} #&&
#   test -e ${boost_stage}/libboost_system-${boost_gxx}-mt.${boost_lib_ext} && 
then
    echo Boost exists.  Skipping
    echo
else
    echo Boost does not exist.  Exitting.
    exit

#    echo Building Boost
#    cd boost_1_36_0
#    ./configure --prefix=`pwd`
#    make -j
#    make install
#    cd ${rootDir}

#    echo Finished making Boost
#    echo
fi

# build ODE
if test -e ${ode_root}/lib/libode.a
then
    echo ODE exists.  Skipping
    echo
else
    echo ODE does not exist.  Exitting.
    exit

#    echo Building ODE
#    cd ode-0.10.1
#    ./configure --prefix=`pwd` --enable-double-precision --with-drawstuff=none --enable-demos=no --with-trimesh=gimpact --enable-malloc #--enable-ou does not work
#    make
#    make install-exec
#    cd ${rootDir}

#    echo Finished making ODE
#    echo
fi




# build HyperNEAT
if test -e ${rootDir}/out/Hypercube_NEAT
then
    echo Hypercube_NEAT exists.  Skipping
    echo
else
    echo Building HyperNEAT
    cd ${rootDir}
    cd HyperNEAT
    rm -rf CMakeFiles CMakeCache.txt cmake_install.cmake
    cmake .
    ccmake -DCMAKE_INSTALL_PREFIX=${rootDir}/out -DJGTL_INCLUDE=${JGTL_include} -DBOOST_ROOT=${boost_root} -DBOOST_STAGE:string=${boost_stage} -DBUILD_PYTHON:bool=OFF -DEXECUTABLE_OUTPUT_PATH=${rootDir}/out -DJGTL_INCLUDE=${JGTL_include} -DLIBRARY_OUTPUT_PATH:string=${rootDir}/hyperneatLibs -DTINYXMLDLL_INCLUDE=${tinyXML_root}/include -DTINYXMLDLL_LIB=${tinyXML_root}/out -DUSE_GUI=OFF -DDRAWSTUFF_INCLUDE:string=${rootDir}/ode-0.10.1/include -DODE_LIB:string=${ode_root}/lib -DODE_INCLUDE:string=${ode_root}/include -DWXWIDGETS_RELEASE_LIB:string=/mnt/home/jclune/hyperneat/hyperneat_libs -DCMAKE_COMPILER_IS_GNUCXX:string=/opt/intel/cce/10.0.025/bin/icpc -DBUILD_MPI:bool=OFF
    make #--debug=v
    cd ${rootDir}

    echo Finished making Hypercube_NEAT
    echo
fi

