#!/usr/bin/python3
# coding=utf-8
# pylint: disable=E1101

""" RPC """

from pylon.core.tools import web, log  # pylint: disable=E0611,E0401,W0611

from tools import auth  # pylint: disable=E0401


def clear_cache(cache, key_getter, target_value):
    """ Clear cache """
    for key in list(cache.keys()):
        log.debug("Cache: %s, key: %s", cache, key)
        #
        key_value = key_getter(key)
        #
        if key_value == target_value:
            cache.pop(key, None)


class RPC:  # pylint: disable=R0903
    """ RPC pseudo-class """

    @web.rpc()
    def invalidate_user_caches(self, user_id):
        """ Invalidate user caches """
        clear_cache(self.user_projects_cache, lambda x: x[1], user_id)
        clear_cache(self.check_public_role_cache, lambda x: x[1], user_id)
        #
        if hasattr(auth, "get_user_permissions_cache"):
            clear_cache(auth.get_user_permissions_cache, lambda x: x[1], user_id)
        if hasattr(auth, "get_user_cache"):
            clear_cache(auth.get_user_cache, lambda x: x[1], user_id)
