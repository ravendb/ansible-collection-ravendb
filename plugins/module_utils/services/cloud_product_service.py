# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


def list_products(client):
    response = client.get("/products/list")
    return response.get("items", [])


def get_product_details(client, product_id):
    return client.get("/products/details/{}".format(product_id))


def filter_products(products, product_id=None, name=None):
    if product_id is not None:
        return [p for p in products if p.get("id") == product_id]
    if name is not None:
        return [p for p in products if p.get("name") == name]
    return list(products)


def enrich_with_details(client, products):
    result = []
    for product in products:
        details = get_product_details(client, product["id"])
        result.append({**product, **details})
    return result
