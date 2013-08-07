import nineml.abstraction_layer as nineml


# parameters = ["Isyn","a", "b", "c", "d", "theta"]


regimes = [
    nineml.Regime(
        "dV/dt = 0.04*V*V + 5*V + 140.0 - U + Isyn",
        "dU/dt = a*(b*V - U)",
        transitions=nineml.On("V > theta", do=["V = c", "U += d", nineml.SpikeOutputEvent]),
        name="subthreshold_regime"
    )]


ports = [nineml.SendPort("V"),
         nineml.ReducePort("Isyn", op="+")]


c1 = nineml.Component("Izhikevich", regimes=regimes)

# write to file object f if defined
try:
    # This case is used in the test suite for examples.
    c1.write(f)
except NameError:
    import os

    base = "izhikevich2"
    c1.write(base + ".xml")
    c2 = nineml.parse(base + ".xml")
    assert c1 == c2

    c1.to_dot(base + ".dot")
    os.system("dot -Tpng %s -o %s" % (base + ".dot", base + ".png"))
