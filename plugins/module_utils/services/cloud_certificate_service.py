# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import os


def download_certificate(client, product_id):
    return client.get_raw("/products/security/certificate/{}".format(product_id))


def read_local(path):
    if os.path.islink(path) or not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        return f.read()


def write_local(path, content):
    if os.path.islink(path):
        raise RuntimeError("Refusing to write certificate: '{}' is a symlink.".format(path))
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, mode=0o700, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
