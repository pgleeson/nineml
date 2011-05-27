
"""
Example of using a cell type defined in 9ML with pyNN.neuron
"""




import sys
from os.path import abspath, realpath, join
import nineml

root = abspath(join(realpath(nineml.__path__[0]), "../../.."))
sys.path.append(join(root, "lib9ml/python/examples/AL"))
sys.path.append(join(root, "code_generation/nmodl"))     
           



from nineml.abstraction_layer.example_models import  get_hierachical_iaf_2coba
from nineml.abstraction_layer.models import ModelToSingleComponentReducer

import pyNN.neuron as sim
from pyNN.neuron.nineml import nineml_cell_type
import pyNN.neuron.nineml as pyNN_nrn_9ml
from pyNN.utility import init_logging


from nineml.abstraction_layer.models.pynn_builder import create_celltypeclass_from_model, CoBaSyn


init_logging(None, debug=True)
sim.setup(timestep=0.1, min_delay=0.1)







from nineml.abstraction_layer.models.pynn_builder import create_celltypeclass_from_model, CoBaSyn

testModel = get_hierachical_iaf_2coba()


celltype_cls = create_celltypeclass_from_model(
                                        name = "iaf_2coba",
                                        nineml_model = testModel,
                                        synapse_components = [
                                            CoBaSyn( namespace='cobaExcit',  weight_connector='q' ),
                                            CoBaSyn( namespace='cobaInhib',  weight_connector='q' ),
                                                   ]
                                        )

parameters = {
    'iaf.cm': 1.0,
    'iaf.gl': 50.0,
    'iaf.taurefrac': 5.0,
    'iaf.vrest': -65.0,
    'iaf.vreset': -65.0,
    'iaf.vthresh': -50.0,
    'cobaExcit.tau': 2.0,
    'cobaInhib.tau': 5.0,
    'cobaExcit.vrev': 0.0,
    'cobaInhib.vrev': -70.0,
}


parameters = ModelToSingleComponentReducer.flatten_namespace_dict( parameters )


cells = sim.Population(1, celltype_cls, parameters)
cells.initialize('iaf_V', parameters['iaf_vrest'])
cells.initialize('tspike', -1e99) # neuron not refractory at start
cells.initialize('regime', 1002) # temporary hack

input = sim.Population(2, sim.SpikeSourcePoisson, {'rate': 100})

connector = sim.OneToOneConnector(weights=1.0, delays=0.5)


conn = [sim.Projection(input[0:1], cells, connector, target='cobaExcit'),
        sim.Projection(input[1:2], cells, connector, target='cobaInhib')]


cells._record('iaf_V')
cells._record('cobaExcit_g')
cells._record('cobaInhib_g')
cells.record()

sim.run(100.0)

cells.recorders['iaf_V'].write("Results/nineml_neuron.V", filter=[cells[0]])
cells.recorders['cobaExcit_g'].write("Results/nineml_neuron.g_exc", filter=[cells[0]])
cells.recorders['cobaInhib_g'].write("Results/nineml_neuron.g_inh", filter=[cells[0]])


t = cells.recorders['iaf_V'].get()[:,1]
v = cells.recorders['iaf_V'].get()[:,2]
gInh = cells.recorders['cobaInhib_g'].get()[:,2]
gExc = cells.recorders['cobaExcit_g'].get()[:,2]

import pylab
pylab.plot(t,v)
pylab.suptitle("From Tree-Model Pathway")
pylab.show()

sim.end()
