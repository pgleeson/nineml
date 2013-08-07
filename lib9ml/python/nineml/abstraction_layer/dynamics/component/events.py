"""
This file contains the definitions for the Events

:copyright: Copyright 2010-2013 by the Python lib9ML team, see AUTHORS.
:license: BSD-3, see LICENSE for details.
"""

from nineml.utility import ensure_valid_c_variable_name


class OutputEvent(object):

    """OutputEvent

    OutputEvents can occur during transitions, and correspond to
    an event being generated on the relevant EventPort port in
    the component.
    """

    def accept_visitor(self, visitor, **kwargs):
        """ |VISITATION| """
        return visitor.visit_outputevent(self, **kwargs)

    def __init__(self, port_name):
        """OutputEvent Constructor

        :param port: The name of the output EventPort that should
            transmit an event. An `EventPort` with a mode of 'send' must exist
            with a corresponding name in the component, otherwise a
            ``NineMLRuntimeException`` will be raised.

        """
        self._port_name = port_name.strip()
        ensure_valid_c_variable_name(self._port_name)

    @property
    def port_name(self):
        '''Returns the name of the port'''
        return self._port_name

    def __str__(self):
        return 'Output Event( port: %s )' % self.port_name
