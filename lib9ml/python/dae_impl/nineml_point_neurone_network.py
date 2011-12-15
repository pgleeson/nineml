#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
.. module:: nineml_point_neurone_network
   :platform: Unix, Windows
   :synopsis: A useful module indeed.

.. moduleauthor:: Dragan Nikolic <dnikolic@incf.org>

"""

from __future__ import print_function
import os, sys, urllib, re, traceback
from time import localtime, strftime

import nineml
from nineml.abstraction_layer import readers
from nineml.abstraction_layer.testing_utils import TestableComponent

from daetools.pyDAE import pyCore, pyActivity, pyDataReporting, pyIDAS, daeLogs
from nineml_component_inspector import nineml_component_inspector
from nineml_daetools_bridge import nineml_daetools_bridge, findObjectInModel, fixObjectName, printComponent
from nineml_tex_report import createLatexReport, createPDF
from nineml_daetools_simulation import daeSimulationInputData, nineml_daetools_simulation, ninemlTesterDataReporter, daetools_model_setup

def fixParametersDictionary(parameters):
    """
    :param parameters: ParameterSet object.
    
    :rtype: A dictionary made of the following key:value pairs: ``{'name' : (value, unit) }``.
    :raises: 
    """
    new_parameters = {}
    for name, parameter in list(parameters.items()):
        new_parameters[name] = (parameter.value, parameter.unit) 
    return new_parameters

def create_nineml_daetools_bridge(name, al_component, parent = None, description = ''):
    """
    Creates 'nineml_daetools_bridge' object for a given AbstractionLayer Component.
    
    :param name: string
    :param al_component: AL Component object
    :param parent: daeModel derived object
    :param description: string
    
    :rtype: nineml_daetools_bridge object
    :raises: RuntimeError 
    """
    return nineml_daetools_bridge(fixObjectName(name), al_component, parent, description)

def create_al_from_ul_component(ul_component):
    """
    Creates AL component referenced in the given UL component.
    Returns the AL Component object. If the url does not point to the xml file with AL components
    (for instance it is an explicit connections file) - the function returns None.
    This is a case when loading ExplicitConnections rule or the url cannot be resolved.
    However, the function always checks if the url is valid and throws an exception if it ain't.
    
    :param ul_component: UL Component object
    
    :rtype: AL Component object
    :raises: RuntimeError 
    """
    try:
        al_component = None
        al_component = nineml.abstraction_layer.readers.XMLReader.read(ul_component.definition.url) 
    
    except Exception as e1:
        # Double-check all this below...
        # Getting an exception can occur for two reasons:
        #  1. The component at the specified URL does not exist
        #  2. The component exists but the parser cannot parse it
        # If the parser couldn't load it try to see if the url is valid and then die miserably
        try:
            f = urllib.urlopen(ul_component.definition.url)
            raise RuntimeError('The component: {0} failed to parse: {1}'.format(ul_component.name, str(e1)))
        
        except Exception as e2:
            raise RuntimeError('Cannot resolve the component: {0}, definition url: {1}, error: {2}'.format(ul_component.name, ul_component.definition.url, str(e2)))
        
        #exc_type, exc_value, exc_traceback = sys.exc_info()
        #strTraceBack = ''.join(traceback.format_tb(exc_traceback))
        #print('********************************************************')
        #print('EXCEPTION', str(e), ul_component.definition.url)
        #print(strTraceBack)
        #print('********************************************************')

    return al_component

class explicit_connections_generator_interface:
    """
    The simplest implementation of the ConnectionGenerator interface (Mikael Djurfeldt)
    built on top of the explicit list of connections.
    
    **Achtung, Achtung!** All indexes are zero-index based, for both source and target populations.
    """
    def __init__(self, connections):
        """
        Initializes the list of connections that the simulator can iterate on.
        
        :param connections: a list of tuples: (int, int) or (int, int, weight) or (int, int, weight, delay) or (int, int, weight, delay, parameters)
    
        :rtype:        
        :raises: RuntimeError 
        """
        if not connections or len(connections) == 0:
            raise RuntimeError('The connections argument is either None or an empty list')
        
        n_values = len(connections[0])
        if n_values < 2:
            raise RuntimeError('The number of items in each connection must be at least 2')
        
        for c in connections:
            if len(c) != n_values:
                raise RuntimeError('An invalid number of items in the connection: {0}; it should be {1}'.format(c, n_values))
        
        self._connections = connections
        self._current     = 0
    
    @property
    def size(self):
        """
        :rtype: Integer (the number of the connections).
        :raises: RuntimeError 
        """
        return len(self._connections)
        
    @property
    def arity(self):
        """
        Returns the number of values stored in an individual connection. It can be zero.
        The first two are always weight and delay; the rest are connection specific parameters.
        
        :rtype: Integer
        :raises: IndexError
        """
        return len(self._connections[0]) - 2
    
    def __iter__(self):
        """
        Initializes and returns the iterator.
        
        :rtype: explicit_connections_generator_interface object (self)
        :raises: 
        """
        self.start()
        return self
    
    def start(self):
        """
        Initializes the iterator.
        
        :rtype:
        :raises: 
        """
        self._current = 0
    
    def next(self):
        """
        Returns the connection and moves the counter to the next one.
        The connection is a tuple: (source_index, target_index, [zero or more floating point values])
        
        :rtype: tuple
        :raises: StopIteration (as required by the python iterator concept)
        """
        if self._current >= len(self._connections):
            raise StopIteration
        
        connection = self._connections[self._current]
        self._current += 1
        
        return connection
        
class daetools_point_neurone_network(pyCore.daeModel):
    """
    A top-level daetools model. All other models will be added to it (neurones, synapses):
     * Neurone names will be: model_name.population_name_Neurone(xxx)
     * Synapse names will be: model_name.projection_name_Synapsexxx(source_index,target_index)
    """
    def __init__(self, model):
        """
        :param model: UL Model object
        :raises: RuntimeError
        """
        name_ = fixObjectName(model.name)
        pyCore.daeModel.__init__(self, name_, None, '')
        
        self._name        = name_
        self._model       = model
        self._components  = {}
        self._groups      = {}
        
        for name, ul_component in list(model.components.items()):
            self._handleComponent(name, ul_component)
        
        for name, group in list(model.groups.items()):
            self._handleGroup(name, group)
    
    def __repr__(self):
        res = 'daetools_point_neurone_network({0})\n'.format(self._name)
        res += '  components:\n'
        for name, o in list(self._components.items()):
            res += '  {0} : {1}\n'.format(name, repr(o))
        res += '  groups:\n'
        for name, o in list(self._groups.items()):
            res += '  {0} : {1}\n'.format(name, repr(o))
        return res

    def getComponent(self, name):
        """
        :param name: string
        :rtype: AL Component object
        :raises: RuntimeError, IndexError
        """
        if not name in self._components:
            raise RuntimeError('Component [{0}] does not exist in the network'.format(name)) 
        return self._components[name][0]

    def getULComponent(self, name):
        """
        :param name: string
        :rtype: UL BaseComponent-derived object
        :raises: RuntimeError, IndexError
        """
        if not name in self._components:
            raise RuntimeError('Component [{0}] does not exist in the network'.format(name)) 
        return self._components[name][1]
    
    def getComponentParameters(self, name):
        """
        :param name: string
        :rtype: dictionary 'name':(value, unit)
        :raises: RuntimeError, IndexError
        """
        if not name in self._components:
            raise RuntimeError('Component [{0}] does not exist in the network'.format(name)) 
        return self._components[name][1].parameters

    def getGroup(self, name):
        """
        :param name: string
        :rtype: daetools_group object
        :raises: RuntimeError
        """
        if not name in self._groups:
            raise RuntimeError('Group [{0}] does not exist in the network'.format(name)) 
        return self._groups[name]

    def DeclareEquations(self):
        """
        Does nothing.
        :rtype:
        :raises:
        """
        pass
    
    def _handleGroup(self, name, ul_group):
        """
        Handles UL Group object:
         * Resolves/creates AL components and their runtime parameters'/initial-conditions' values.
         * Creates populations of neurones and adds them to the 'neuronePopulations' dictionary
         * Creates projections and adds them to the 'projections' dictionary
        
        :param name: string
        :param ul_group: UL Group object
        
        :rtype:
        :raises: RuntimeError
        """
        group = daetools_group(name, ul_group, self) 
        self._groups[name] = group
    
    def _handleComponent(self, name, ul_component):
        """
        Resolves UL component and adds AL Component object to the list.
        :param name: string
        :param ul_component: UL BaseComponent-derived object
        
        :rtype:        
        :raises: RuntimeError
        """
        al_component = create_al_from_ul_component(ul_component) 
        self._components[name] = (al_component, ul_component)

class daetools_group:
    """
    """
    def __init__(self, name, ul_group, network):
        """
        :param name: string
        :param ul_group: UL Group object
        :param network: daetools_point_neurone_network object
        
        :rtype:
        :raises: RuntimeError
        """
        self._name        = fixObjectName(name)
        self._network     = network
        self._populations = {}
        self._projections = {}
        
        for name, ul_population in list(ul_group.populations.items()):
            self._handlePopulation(name, ul_population, network)
        
        for name, ul_projection in list(ul_group.projections.items()):
            self._handleProjection(name, ul_projection, network)
    
    def __repr__(self):
        res = 'daetools_group({0})\n'.format(self._name)
        res += '  populations:\n'
        for name, o in list(self._populations.items()):
            res += '  {0} : {1}\n'.format(name, repr(o))
        res += '  projections:\n'
        for name, o in list(self._projections.items()):
            res += '  {0} : {1}\n'.format(name, repr(o))
        return res

    def getPopulation(self, name):
        """
        :param name: string
        :rtype: daetools_population object
        :raises: RuntimeError
        """
        if not name in self._populations:
            raise RuntimeError('Population [{0}] does not exist in the group'.format(name)) 
        return self._populations[name]
        
    def getProjection(self, name):
        """
        :param name: string
        :rtype: daetools_projection object
        :raises: RuntimeError
        """
        if not name in self._projections:
            raise RuntimeError('Projection [{0}] does not exist in the group'.format(name)) 
        return self._projections[name]
    
    def _handlePopulation(self, name, ul_population, network):
        """
        Handles UL Population object:
         * Creates 'nineml_daetools_bridge' object for each neurone in the population
        
        :param name: string
        :param ul_population: UL Population object
        
        :rtype: None
        :raises: RuntimeError
        """
        population = daetools_population(name, ul_population, network) 
        self._populations[name] = population
    
    def _handleProjection(self, name, ul_projection, network):
        """
        Handles a NineML UserLayer Projection object:
         * Creates connections between a source and a target neurone via PSR component.
           PSR components are first transformed into the 'nineml_daetools_bridge' objects
        
        :param name: string
        :param ul_projection: UL Projection object
        
        :rtype:
        :raises: RuntimeError
        """
        projection = daetools_projection(name, ul_projection, self, network) 
        self._projections[name] = projection

class daetools_population:
    """
    """
    def __init__(self, name, ul_population, network):
        """
        :param name: string
        :param ul_population: UL Population object
        :param network: daetools_point_neurone_network object
        
        :rtype: 
        :raises: RuntimeError
        """
        self._name       = fixObjectName(name)
        self._network    = network
        self._parameters = fixParametersDictionary(ul_population.prototype.parameters)
        self._neurones   = []
        self._positions  = []
        
        # Get the AL component from the network
        al_component = network.getComponent(ul_population.prototype.name) 
        
        for i in range(0, ul_population.number):
            neurone = create_nineml_daetools_bridge('{0}_Neurone({1})'.format(self._name, i), al_component, network, '')
            self._neurones.append(neurone)
        
        try:
            self._positions = ul_population.positions.get_positions(ul_population)
        except Exception as e:
            print(str(e))
        
    def getNeurone(self, index):
        """
        :param name: integer
        :rtype: None
        :raises: IndexError
        """
        return self._neurones[int(index)]
    
    def __repr__(self):
        res = 'daetools_population({0})\n'.format(self._name)
        res += '  neurones:\n'
        for o in self._neurones:
            res += '  {0}\n'.format(repr(o))
        return res

class daetools_projection:
    """
    Data members:    
     * _name                  : string
     * _source_population     : daetools_population
     * _target_population     : daetools_population
     * _psr                   : AL Component
     * _connection_type       : AL Component
     * _connection_rule       : AL component
     * _generated_connections : list of ...
    """
    def __init__(self, name, ul_projection, group, network):
        """
        :param name: string
        :param ul_projection: UL Projection object
        :param group: daetools_group object
        :param network: daetools_point_neurone_network object
        
        :rtype:
        :raises: RuntimeError
        """
        self._name                  = fixObjectName(name)
        self._network               = network
        self._source_population     = group.getPopulation(ul_projection.source.name)
        self._target_population     = group.getPopulation(ul_projection.target.name)
        self._psr                   = network.getComponent(ul_projection.synaptic_response.name)
        self._psr_parameters        = fixParametersDictionary(ul_projection.synaptic_response.parameters)
        self._connection_rule       = network.getComponent(ul_projection.rule.name)
        self._connection_type       = network.getComponent(ul_projection.connection_type.name)
        self._generated_connections = []
        
        ul_connection_rule = network.getULComponent(ul_projection.rule.name)
        if hasattr(ul_connection_rule, 'connections'): # Explicit connections
            connections = getattr(ul_connection_rule, 'connections') 
            cgi = explicit_connections_generator_interface(connections)
            self._createConnections(cgi)
        
        else: # It should be the CSA component then
            self._handleConnectionRuleComponent(self._connection_rule)
        
    def __repr__(self):
        res = 'daetools_projection({0})\n'.format(self._name)
        res += '  source_population:\n'
        res += '    {0}\n'.format(self._source_population)
        res += '  target_population:\n'
        res += '    {0}\n'.format(self._target_population)
        res += '  psr:\n'
        res += '    {0}\n'.format(self._psr)
        res += '  connection_rule:\n'
        res += '    {0}\n'.format(self._connection_rule)
        res += '  connection_type:\n'
        res += '    {0}\n'.format(self._connection_type)
        return res

    def _handleConnectionRuleComponent(self, al_connection_rule):
        """
        :param al_connection_rule: AL Component object (CSA or other)
        
        :rtype: None
        :raises: RuntimeError
        """
        raise RuntimeError('Support for connection rule component not implemented yet')

    def _createConnections(self, cgi):
        """
        Iterates over ConnectionGeneratorInterface object and creates connections.
        Based on the connections, connects source->target neurones and (optionally) sets weights and delays
        
        :param cgi: ConnectionGeneratorInterface object
        
        :rtype: None
        :raises: RuntimeError
        """
        count        = 0
        connections  = []
        
        for connection in cgi:
            size = len(connection)
            if(size < 2):
                raise RuntimeError('Not enough data in the explicit lists of connections')
            
            source_index = int(connection[0])
            target_index = int(connection[1])
            weight       = 0.0
            delay        = 0.0
            parameters   = []
            
            if cgi.arity == 1:
                weight = float(connection[2])
            elif cgi.arity == 2:
                weight = float(connection[2])
                delay  = float(connection[3])
            elif cgi.arity >= 3:
                weight = float(connection[2])
                delay  = float(connection[3])
                for i in range(4, size):
                    parameters.append(float(connection[i]))           
            
            self._createConnection(source_index, target_index, weight, delay, parameters, count)
            connections.append( (source_index, target_index, weight, delay, parameters) )
            count += 1
        
        for c in connections:
            print(c)

    def _createConnection(self, source_index, target_index, weight, delay, parameters, n):
        """
        Connects a source and a target neurone via the psr component.
        First tries to obtain the source/target neurone objects from the corresponding populations, 
        then creates the nineml_daetools_bridge object for the synapse component and finally tries 
        to connect event ports between the source neurone and the synapse and analogue ports between
        the synapse and the target neurone. The source neurone, the synapse and the target neurone 
        are appended to the list of generated connections.
        
        :param source_index: integer; index in the source population
        :param target_index: integer; index in the target population
        :param weight: float
        :param delay: float
        :param n: number of connections in the projection (just to format the name of the synapse)
        
        :rtype: None
        :raises: RuntimeError
        """
        source_neurone = self._source_population.getNeurone(source_index)
        target_neurone = self._target_population.getNeurone(target_index)
        
        synapse_name   = '{0}_Synapse{1}({2},{3})'.format(self._name, n, int(source_index), int(target_index))
        synapse        = create_nineml_daetools_bridge(synapse_name, self._psr, self._network, '')
        
        nineml_daetools_bridge.connectModelsViaEventPort    (source_neurone, synapse,        self._network)
        nineml_daetools_bridge.connectModelsViaAnaloguePorts(synapse,        target_neurone, self._network)
        
        self._generated_connections.append( (source_neurone, synapse, target_neurone) )

class nineml_daetools_network_simulation(pyActivity.daeSimulation):
    """
    """
    def __init__(self, network):
        """
        :rtype: None
        :raises: RuntimeError
        """
        pyActivity.daeSimulation.__init__(self)
        
        self.m = network
        self.model_setups = []
        
        event_ports_expressions = {"spikeinput": "0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90"} 
        for name, group in network._groups.items():
            # Setup neurones in populations
            for name, population in group._populations.items():
                for neurone in population._neurones:
                    initial_values = population._parameters
                    setup = daetools_model_setup(neurone, False, parameters              = initial_values, 
                                                                 initial_conditions      = initial_values,
                                                                 event_ports_expressions = event_ports_expressions)
                    self.model_setups.append(setup)
        
            for name, projection in group._projections.items():
                # Setup synapses 
                initial_values = projection._psr_parameters
                for s, synapse, t in projection._generated_connections:
                    setup = daetools_model_setup(synapse, False, parameters         = initial_values, 
                                                                 initial_conditions = initial_values)
                    self.model_setups.append(setup)

    def SetUpParametersAndDomains(self):
        """
        :rtype: None
        :raises: RuntimeError
        """
        for s in self.model_setups:
            s.SetUpParametersAndDomains()
        
    def SetUpVariables(self):
        """
        :rtype: None
        :raises: RuntimeError
        """
        for s in self.model_setups:
            s.SetUpVariables()

def pyNN_example():
    """
    Example: Simple random network with a 1D population of Poisson spike sources projecting to a 2D population of IF_curr_alpha neurons.
    Simple network with a 1D population of poisson spike sources projecting to a 2D population of IF_curr_exp neurons.

    Andrew Davison, UNIC, CNRS
    August 2006, November 2009

    $Id: simpleRandomNetwork.py 894 2011-01-11 11:36:46Z apdavison $
    """

    import socket

    from pyNN.utility import get_script_args

    simulator_name = "neuron" # neuron nest
    exec("from pyNN.%s import *" % simulator_name)

    from pyNN.random import NumpyRNG

    no_cells1 = 10
    no_cells2 = 10
    seed = 764756387
    tstop = 1000.0 # ms
    input_rate = 100.0 # Hz
    cell_params = {'tau_refrac': 2.0,  # ms
                   'v_thresh':  -50.0, # mV
                   'tau_syn_E':  2.0,  # ms
                   'tau_syn_I':  2.0}  # ms
    n_record = 5

    node = setup(timestep=0.025, min_delay=1.0, max_delay=1.0, debug=True, quit_on_end=False)
    print( "Process with rank %d running on %s" % (node, socket.gethostname()) )


    rng = NumpyRNG(seed=seed, parallel_safe=True)

    print( "[%d] Creating populations" % node )
    n_spikes = int(2*tstop*input_rate/1000.0)
    spike_times = numpy.add.accumulate(rng.next(n_spikes, 'exponential',
                                                [1000.0/input_rate], mask_local=False))
    print( "[%d] spike_times: [%s]" % (node, str(spike_times)) )

    input_population  = Population(no_cells1, SpikeSourceArray, {'spike_times': spike_times }, label="input")
    output_population = Population(no_cells2, IF_curr_exp, cell_params, label="output")
    print( "[%d] input_population cells: %s" % (node, input_population.local_cells) )
    print( "[%d] output_population cells: %s" % (node, output_population.local_cells) )

    print( "[%d] Connecting populations" % node )
    connector = FixedProbabilityConnector(0.5, weights=1.0)
    projection = Projection(input_population, output_population, connector, rng=rng)

    file_stem = "Results/simpleRandomNetwork_np%d_%s" % (num_processes(), simulator_name)
    projection.saveConnections('%s.conn' % file_stem)

    input_population.record()
    output_population.record()
    output_population.sample(n_record, rng).record_v()

    print( "[%d] Running simulation" % node )
    run(tstop)

    print( "[%d] Writing spikes to disk" % node )
    output_population.printSpikes('%s_output.ras' % file_stem)
    input_population.printSpikes('%s_input.ras' % file_stem)
    print( "[%d] Writing Vm to disk" % node )
    output_population.print_v('%s.v' % file_stem)

    print( "[%d] Finishing" % node )
    end()
    print( "[%d] Done" % node )


if __name__ == "__main__":
    #import numpy
    #numpy.random.seed(1234)

    #sources_ex = numpy.random.random_integers(0, 20, 10)
    #sources_in = numpy.random.random_integers(0, 20, 10)
    #print(sources_ex)
    #print(sources_in)
    #pyNN_example()
    #exit(1)
    
    catalog = "file:///home/ciroki/Data/NineML/nineml-model-tree/lib9ml/python/dae_impl/"

    neurone_params = {
                       'tspike' :    ( -1.000, 's'),
                       'V' :         ( -0.060, 'V'),
                       'gl' :        ( 50.000, 'S/(m^2)'),
                       'vreset' :    ( -0.060, 'V'),
                       'taurefrac' : (  0.001, 's'),
                       'vthresh' :   ( -0.040, 'V'),
                       'vrest' :     ( -0.060, 'V'),
                       'cm' :        (100.000, 'F/(m^2)')
                     }
    
    psr_excitatory_params = {
                             'vrev' : ( 0.000, 'V'),
                             'q'    : ( 0.270, 'S'),
                             'tau'  : ( 0.005, 's'),
                             'g'    : ( 0.000, 'A/V')
                            }
                     
    psr_inhibitory_params = {
                             'vrev' : (-0.080, 'V'),
                             'q'    : ( 4.500, 'S'),
                             'tau'  : ( 0.010, 's'),
                             'g'    : ( 0.000, 'A/V')
                            }
    
    neurone_IAF = nineml.user_layer.SpikingNodeType("IAF neurones", catalog + "iaf.xml", neurone_params)
    
    psr_excitatory  = nineml.user_layer.SynapseType   ("COBA excitatory", catalog + "coba_synapse.xml", psr_excitatory_params)
    psr_inhibitory  = nineml.user_layer.SynapseType   ("COBA inhibitory", catalog + "coba_synapse.xml", psr_inhibitory_params)
    
    grid2D          = nineml.user_layer.Structure("2D grid", catalog + "2Dgrid.xml")
    connection_type = nineml.user_layer.ConnectionType("Static weights and delays", catalog + "static_weights_delays.xml")
    
    population_excitatory = nineml.user_layer.Population("Excitatory population", 4000, neurone_IAF, nineml.user_layer.PositionList(structure=grid2D))
    population_inhibitory = nineml.user_layer.Population("Inhibitory population", 1000, neurone_IAF, nineml.user_layer.PositionList(structure=grid2D))

    connections_exc_exc = [(0,0,1.0,1.0),
                           (9,9,1.0,1.0)
                          ]
    connections_exc_inh = [(0,0,1.0,1.0),
                           (9,9,1.0,1.0)
                          ]
    connections_inh_inh = [(0,0,1.0,1.0),
                           (9,9,1.0,1.0)
                          ]
    connections_inh_exc = [(0,0,1.0,1.0),
                           (9,9,1.0,1.0)
                          ]
    connection_rule_exc_exc = nineml.user_layer.ConnectionRule("Explicit Connections exc_exc", catalog + "explicit_list_of_connections.xml")
    connection_rule_exc_inh = nineml.user_layer.ConnectionRule("Explicit Connections exc_inh", catalog + "explicit_list_of_connections.xml")
    connection_rule_inh_inh = nineml.user_layer.ConnectionRule("Explicit Connections inh_inh", catalog + "explicit_list_of_connections.xml")
    connection_rule_inh_exc = nineml.user_layer.ConnectionRule("Explicit Connections inh_exc", catalog + "explicit_list_of_connections.xml")
    
    setattr(connection_rule_exc_exc, 'connections', connections_exc_exc)
    setattr(connection_rule_exc_inh, 'connections', connections_exc_inh)
    setattr(connection_rule_inh_inh, 'connections', connections_inh_inh)
    setattr(connection_rule_inh_exc, 'connections', connections_inh_exc)

    projection_exc_exc = nineml.user_layer.Projection("Projection exc_exc", population_excitatory, population_excitatory, connection_rule_exc_exc, psr_excitatory, connection_type)
    projection_exc_inh = nineml.user_layer.Projection("Projection exc_inh", population_excitatory, population_inhibitory, connection_rule_exc_inh, psr_excitatory, connection_type)
    projection_inh_inh = nineml.user_layer.Projection("Projection inh_inh", population_inhibitory, population_inhibitory, connection_rule_inh_inh, psr_inhibitory, connection_type)
    projection_exc_exc = nineml.user_layer.Projection("Projection inh_exc", population_inhibitory, population_excitatory, connection_rule_inh_exc, psr_inhibitory, connection_type)

    # Add everything to a single group
    network = nineml.user_layer.Group("Network")
    
    # Add populations
    network.add(population_excitatory)
    network.add(population_inhibitory)
    
    # Add projections
    network.add(projection_exc_exc)
    network.add(projection_exc_inh)
    network.add(projection_inh_inh)
    network.add(projection_exc_exc)

    # Create a network and add the group to it
    model = nineml.user_layer.Model("Simple 9ML example model")
    model.add_group(network)
    model.write("Brette et al., J. Computational Neuroscience (2007).xml")
    
    network = daetools_point_neurone_network(model)
    #print(network)
    #exit(0)

    # Create Log, Solver, DataReporter and Simulation object
    from daetools.solvers import pySuperLU

    log          = daeLogs.daePythonStdOutLog()
    daesolver    = pyIDAS.daeIDAS()
    datareporter = pyDataReporting.daeTCPIPDataReporter()
    simulation   = nineml_daetools_network_simulation(network)
    
    lasolver     = pySuperLU.daeCreateSuperLUSolver()
    daesolver.SetLASolver(lasolver)

    # Set the time horizon and the reporting interval
    simulation.ReportingInterval = 0.1
    simulation.TimeHorizon       = 1.0

    # Connect data reporter
    simName = simulation.m.Name + strftime(" [%d.%m.%Y %H:%M:%S]", localtime())
    if(datareporter.Connect("", simName) == False):
        sys.exit()

    # Initialize the simulation
    simulation.Initialize(daesolver, datareporter, log)

    # Solve at time=0 (initialization)
    simulation.SolveInitial()

    # Run
    simulation.Run()
    simulation.Finalize()

"""
class IF_cond_exp(StandardCellType):
    Leaky integrate and fire model with fixed threshold and 
    exponentially-decaying post-synaptic conductance.
    
    default_parameters = {
        'v_rest'     : -65.0,   # Resting membrane potential in mV. 
        'cm'         : 1.0,     # Capacity of the membrane in nF
        'tau_m'      : 20.0,    # Membrane time constant in ms.
        'tau_refrac' : 0.1,     # Duration of refractory period in ms.
        'tau_syn_E'  : 5.0,     # Decay time of the excitatory synaptic conductance in ms.
        'tau_syn_I'  : 5.0,     # Decay time of the inhibitory synaptic conductance in ms.
        'e_rev_E'    : 0.0,     # Reversal potential for excitatory input in mV
        'e_rev_I'    : -70.0,   # Reversal potential for inhibitory input in mV
        'v_thresh'   : -50.0,   # Spike threshold in mV.
        'v_reset'    : -65.0,   # Reset potential after a spike in mV.
        'i_offset'   : 0.0,     # Offset current in nA
    }
    recordable = ['spikes', 'v', 'gsyn']
    default_initial_values = {
        'v': -65.0, #'v_rest',
    }

Leaky_iaf:
def get_component():
    subthreshold_regime = al.Regime(
        name="subthreshold_regime",
        time_derivatives =[ "dV/dt = (-gL*(V-vL) + Isyn)/C",],
        transitions = [al.On("V> theta",
                                do=["t_spike = t", "V = V_reset",
                                    al.OutputEvent('spikeoutput')],
                                to="refractory_regime") ],
        )

    refractory_regime = al.Regime(
        transitions = [al.On("t >= t_spike + t_ref",
                                to='subthreshold_regime')],
        name="refractory_regime"
        )

    analog_ports = [al.SendPort("V"),
             al.ReducePort("Isyn",reduce_op="+")]

    c1 = al.ComponentClass("LeakyIAF", regimes = [subthreshold_regime, refractory_regime], analog_ports=analog_ports)

    return c1
"""