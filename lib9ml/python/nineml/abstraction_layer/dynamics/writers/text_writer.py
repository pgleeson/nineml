"""
docstring needed

:copyright: Copyright 2010-2013 by the Python lib9ML team, see AUTHORS.
:license: BSD-3, see LICENSE for details.
"""

from nineml.abstraction_layer.dynamics import flattening


def dump_reduced(component, filename):
    pass

tmpl = """
    MODEL:

    PORTS:
    ==========

    #for p in $component.analog_ports:
      AnalogPort: $p.name, $p.mode, $p.reduce_op
    #end for

    #for p in $component.event_ports:
      EventPort: $p.name, $p.mode, $p.reduce_op
    #end for


    PARAMETERS:
    ===========
    #for up in $component.parameters:
      Parameter: $up
    #end for


    Aliases:
    ========
    #for b in $component.aliases:
        Alias: $b
    #end for


    State Variables:
    =================
    #for s in $component.state_variables:
        State Variable: $s
    #end for

    REGIMES:
    ========
    #for regime in $component.regimes:

    Regime: $regime
    ----------------

    #for eqn in $regime.time_derivatives:
       TimeDeriv: $eqn
    #end for

        OnEvents:
        ~~~~~~~~~~~~~~

#*
        #for $on_event in $regime.on_events:
           Event: $on_event.src_port_name [To -> $on_event.to ]
           #for node in $on_event.nodes:
             Node: $node
           #end for
        #end for

        OnConditions:
        ~~~~~~~~~~~~~~
        #for $on_condition in $regime.on_conditions:
           Event: $on_condition.trigger [To -> $on_event.to ]
           #for node in $on_condition.nodes:
             Node: $node
           #end for
        #end for
*#


    #end for



    """


class TextWriter(object):

    """TextWriter DocString"""

    @classmethod
    def write(cls, component, filename):

        if not component.is_flat():
            component = flattening.flatten(component)

        from Cheetah.Template import Template
        data = {'component': component}
        f = open(filename, "w")
        s = Template(tmpl, data).respond()
        f.write(s)
        f.close()
