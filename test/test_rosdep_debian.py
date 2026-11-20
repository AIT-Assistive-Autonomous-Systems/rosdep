# Copyright (c) 2011, Willow Garage, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the Willow Garage, Inc. nor the names of its
#       contributors may be used to endorse or promote products derived from
#       this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# Author Ken Conley/kwc@willowgarage.com

import os
import subprocess
import traceback
from unittest.mock import Mock, patch, call


def get_test_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), 'debian'))


@patch('rosdep2.platforms.debian.apt_satisfy_available', return_value=False)
def test_dpkg_detect(mock_satisfy):
    from rosdep2.platforms.debian import dpkg_detect

    with patch('rosdep2.platforms.debian.read_stdout') as mock_read_stdout:
        mock_read_stdout.side_effect = [('', ''), '']
        val = dpkg_detect([])
        assert val == [], val
        assert mock_read_stdout.call_count == 2
        assert mock_read_stdout.call_args_list[0] == call(['dpkg-query', '-W', "-f='${Package} ${Status}\n'"], True)
        assert mock_read_stdout.call_args_list[1] == call(['apt-cache', 'showpkg'])

    with patch('rosdep2.platforms.debian.read_stdout') as mock_read_stdout:
        mock_read_stdout.side_effect = [('', ''), '']
        val = dpkg_detect(['tinyxml-dev'])
        assert val == [], val
        assert mock_read_stdout.call_count == 2
        assert mock_read_stdout.call_args_list[0] == call(['dpkg-query', '-W', "-f='${Package} ${Status}\n'",
                                                           'tinyxml-dev'], True)
        assert mock_read_stdout.call_args_list[1] == call(['apt-cache', 'showpkg', 'tinyxml-dev'])

    with open(os.path.join(get_test_dir(), 'dpkg-python-apt'), 'r') as f:
        dpkg_python_apt_test_content = f.read()

    with patch('rosdep2.platforms.debian.read_stdout') as mock_read_stdout:
        mock_read_stdout.side_effect = [(dpkg_python_apt_test_content, ''), '']
        val = dpkg_detect(['apt', 'tinyxml-dev', 'python'])
        assert val == ['apt', 'python'], val
        assert mock_read_stdout.call_count == 2
        print(mock_read_stdout.call_args_list[0])
        assert mock_read_stdout.call_args_list[1] == call(['apt-cache', 'showpkg', 'tinyxml-dev'])

    # test version lock code (should be filtered out w/o validation)
    with patch('rosdep2.platforms.debian.read_stdout') as mock_read_stdout:
        mock_read_stdout.side_effect = [(dpkg_python_apt_test_content, ''), '']
        val = dpkg_detect(['apt=1.8', 'tinyxml-dev', 'python=2.7'])
        assert val == ['apt=1.8', 'python=2.7'], val
        assert mock_read_stdout.call_count == 2
        assert mock_read_stdout.call_args_list[1] == call(['apt-cache', 'showpkg', 'tinyxml-dev'])


def test_read_apt_cache_showpkg():
    from rosdep2.platforms.debian import _read_apt_cache_showpkg

    m = Mock()
    with open(os.path.join(get_test_dir(), 'showpkg-curl-wget-libcurl-dev'), 'r') as f:
        m.return_value = f.read()
    pkgs = ['curl', 'wget', '_not_existing', 'libcurl-dev', 'ros-kinetic-rc-genicam-api']
    results = list(_read_apt_cache_showpkg(pkgs, exec_fn=m))
    assert len(results) == len(pkgs), results

    package, virtual, providers = results[0]
    assert package == 'curl', package
    assert not virtual
    assert providers is None, providers

    package, virtual, providers = results[1]
    assert package == 'wget', package
    assert not virtual
    assert providers is None, providers

    package, virtual, providers = results[2]
    assert package == '_not_existing', package
    assert not virtual
    assert providers is None, providers

    package, virtual, providers = results[3]
    assert package == 'libcurl-dev', package
    assert virtual, providers

    package, virtual, providers = results[4]
    assert package == 'ros-kinetic-rc-genicam-api', package
    assert not virtual
    assert providers is None, providers


def test_AptInstaller():
    from rosdep2.platforms.debian import AptInstaller

    @patch('rosdep2.platforms.debian.apt_satisfy_available', return_value=False)
    @patch('rosdep2.platforms.debian.read_stdout')
    @patch.object(AptInstaller, 'get_packages_to_install')
    def test(expected_prefix, mock_get_packages_to_install, mock_read_stdout, mock_satisfy):
        installer = AptInstaller()
        mock_get_packages_to_install.return_value = []
        mock_read_stdout.return_value = ''
        assert [] == installer.get_install_command(['fake'])

        mock_get_packages_to_install.return_value = ['a', 'b']
        expected = [expected_prefix + ['apt-get', 'install', '-y', 'a'],
                    expected_prefix + ['apt-get', 'install', '-y', 'b']]
        val = installer.get_install_command(['whatever'], interactive=False)
        print('VAL', val)
        assert val == expected, val
        expected = [expected_prefix + ['apt-get', 'install', 'a'],
                    expected_prefix + ['apt-get', 'install', 'b']]
        val = installer.get_install_command(['whatever'], interactive=True)
        assert val == expected, val
    try:
        if hasattr(os, 'geteuid'):
            with patch('rosdep2.installers.os.geteuid', return_value=1):
                test(['sudo', '-H'])
            with patch('rosdep2.installers.os.geteuid', return_value=0):
                test([])
        else:
            test([])
    except AssertionError:
        traceback.print_exc()
        raise


def test_is_dependency_relation():
    from rosdep2.platforms.debian import is_dependency_relation

    assert not is_dependency_relation('libfoo-dev')
    assert not is_dependency_relation('libeigen3-dev=3.0.1-*')
    assert is_dependency_relation('libfoo1 | libfoo2')
    assert is_dependency_relation('libfoo-dev (>= 1.2)')
    assert is_dependency_relation('libfoo-dev, libbar-dev')


def test_dpkg_detect_apt():
    # apt >= 2.1: satisfied if apt-get satisfy --simulate changes nothing
    from rosdep2.platforms.debian import dpkg_detect

    outputs = {
        ('a | b (>= 1)',): ('0 upgraded, 0 newly installed\n', ''),
        ('name',): ('0 upgraded, 0 newly installed\n', ''),  # name=version: only the name is checked
        ('c (>= 2)',): ('Inst c (2.1 repo [amd64])\nConf c (2.1 repo [amd64])\n', ''),
        ('d',): ('', 'E: Unable to satisfy dependencies.\n'),
        ('e',): ('Remv f (1.0 [amd64])\n', ''),
    }
    exec_fn = Mock(side_effect=lambda cmd, capture_stderr: outputs.get(
        tuple(cmd[3:]), ('0 upgraded, 0 newly installed\n', '')))
    with patch('rosdep2.platforms.debian.apt_satisfy_available', return_value=True):
        # all satisfied: a single apt call
        assert dpkg_detect(['a | b (>= 1)', 'x'], exec_fn) == ['a | b (>= 1)', 'x']
        assert exec_fn.call_args_list == [call(['apt-get', 'satisfy', '--simulate', 'a | b (>= 1)', 'x'], True)]
        # something missing: each on its own
        outputs[('a | b (>= 1)', 'name', 'c (>= 2)', 'd', 'e')] = ('Inst c (2.1 repo [amd64])\n', '')
        assert dpkg_detect(['a | b (>= 1)', 'name=1.0-*', 'c (>= 2)', 'd', 'e'], exec_fn) == [
            'a | b (>= 1)', 'name=1.0-*']


def test_dpkg_detect_without_satisfy():
    # no apt-get satisfy (apt < 2.1): original detection, relations are not found
    from rosdep2.platforms.debian import dpkg_detect

    with patch('rosdep2.platforms.debian.apt_satisfy_available', return_value=False), \
            patch('rosdep2.platforms.debian.read_stdout') as mock_read_stdout:
        mock_read_stdout.side_effect = [('c install ok installed\n', ''), '']
        assert dpkg_detect(['a | b', 'c']) == ['c']


def test_AptInstaller_satisfy():
    from rosdep2.platforms.debian import AptInstaller

    with patch('rosdep2.installers.os.geteuid', return_value=0), \
            patch('rosdep2.platforms.debian.apt_satisfy_available', return_value=True), \
            patch('rosdep2.platforms.debian.read_stdout', return_value=''), \
            patch.object(AptInstaller, 'get_packages_to_install') as mock_get_packages_to_install:
        installer = AptInstaller()
        mock_get_packages_to_install.return_value = ['a', 'b | c (>= 1)', 'e=1.0-*', 'd (>= 1), d (<< 2~)']
        assert installer.get_install_command(['whatever'], interactive=False, quiet=True) == [
            ['apt-get', 'install', '-y', '-qq', 'e=1.0-*'],
            ['apt-get', 'satisfy', '-y', '-qq', 'a', 'b | c (>= 1)', 'd (>= 1), d (<< 2~)'],
        ]
        mock_get_packages_to_install.return_value = ['b | c']
        assert installer.get_install_command(['whatever']) == [['apt-get', 'satisfy', 'b | c']]


def test_AptInstaller_relations_without_satisfy():
    from rosdep2.core import InstallFailed
    from rosdep2.platforms.debian import AptInstaller

    with patch('rosdep2.platforms.debian.apt_satisfy_available', return_value=False), \
            patch.object(AptInstaller, 'get_packages_to_install', return_value=['a', 'b | c']):
        try:
            AptInstaller().get_install_command(['whatever'])
            assert False, 'expected InstallFailed'
        except InstallFailed as e:
            assert 'apt-get satisfy' in str(e) and 'b | c' in str(e)
