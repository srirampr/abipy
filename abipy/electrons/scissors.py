from __future__ import print_function, division

import numpy as np
import cPickle as pickle

from collections import OrderedDict
from abipy.tools import AttrDict

__all__ = [
    "Scissors",
    "ScissorsBuilder"
]


class ScissorsError(Exception):
    """Base class for the exceptions raised by `Scissors`"""


class Scissors(object):
    """
    This object represents an energy-dependent scissors operator.
    The operator is defined by a list of domains (energy intervals)
    and a list of functions defined on these domains. The domains
    should fulfill the constraints documented in the main constructor.
    We assume eV units everywhere.

    The standard way to create this object is via the methods
    provided by the factory class `ScissorBuilder`.
    Once the instance has been create, one can correct the
    band structure by calling the `apply` method.
    """
    Error = ScissorsError

    def __init__(self, func_list, domains, bounds=None):
        """
        Args:
            func_list:
                List of callable objects.
            domains:
                 Domains of each function. List of tuples [(emin1, emax1), (emin2, emax2), ...]
            bounds:
                Boundaries

        .. note:

            - Domains should not overlap, cover e0mesh, and given in increasing order.

            - Holes are permitted but the interpolation will raise an exception if the
              eigenvalue falls inside the hole.
        """
        # TODO Add consistency check.
        self.func_list = func_list
        self.domains = np.atleast_2d(domains)
        assert len(self.func_list) == len(self.domains)

        # Treat the out-of-boundary conditions.
        blow, bhigh  = "c", "c"
        if bounds is not None:
            blow  = bounds[0][0]
            bhigh = bounds[0][1]

        if blow.lower() == "c":
            try:
                self.func_low = lambda x: float(bounds[0][1])

            except:
                x_low = self.domains[0,0]
                fx_low = func_list[0](x_low)
                self.func_low = lambda x: fx_low
        else:
            raise NotImplementedError("Only constant boundaries are implemented")

        if bhigh.lower() == "c":
            try:
                self.func_high = lambda x: float(bounds[1][1])

            except:
                x_high  = self.domains[1, -1]
                fx_high = func_list[-1](x_high)
                self.func_high = lambda x: fx_high
        else:
            raise NotImplementedError("Only constant boundaries are implemented")

        # Init the internal counter.
        self.out_bounds = np.zeros(3, np.int)

    def apply(self, eig):
        """Correct the eigenvalue eig (eV units)."""
        domains = self.domains

        if eig < domains[0,0]:
            print("left ", eig, domains[0,0])
            self.out_bounds[0] += 1
            return self.func_low(eig)

        if eig > domains[-1,1]:
            print("right ", eig, domains[-1,1])
            self.out_bounds[1] += 1
            return self.func_high(eig)

        for idx, dms in enumerate(domains):
            if dms[1] >= eig >= dms[0]:
                return self.func_list[idx](eig)

        self.out_bounds[2] += 1
        raise self.Error("Cannot bracket eigenvalue %s" % eig)


class ScissorsBuilder(object):
    """
    This object facilitates the creations of `Scissors` instances.
    """
    _DEBUG = True

    def __init__(self, qps_spin):
        # Sort quasiparticle data by e0.
        qpsort = []
        for qps in qps_spin:
            qpsort.append(qps.sort_by_e0())

        self._qps_spin = tuple(qpsort)

        # Compute the boundaries of the E0 mesh.
        e0min, e0max = np.inf, -np.inf
        for qps in self._qps_spin:
            e0mesh = qps.get_e0mesh()
            e0min = min(e0min, e0mesh[0]) 
            e0max = max(e0max, e0mesh[-1])

        self._e0min, self._e0max = e0min, e0max

        # The parameters defining the scissors operator
        self.domains_spin = OrderedDict()
        self.bounds_spin = OrderedDict()

    @classmethod
    def from_file(cls, filepath):
        """Generate an instance of ScissorsBuilder from file."""
        from abipy.abilab import abiopen
        ncfile = abiopen(filepath)
        return cls(qps_spin=ncfile.qplist_spin)

    @property
    def nsppol(self):
        """Number of spins."""
        return len(self._qps_spin)

    @property
    def e0min(self):
        """Minimum KS energy."""
        return self._e0min

    @property
    def e0max(self):
        """Maximum KS energy."""
        return self._e0max

    def get_scissors_spin(self):
        """Returns a tuple of `Scissors` indexed by the spin value."""
        try:
            return self._scissors_spin
        except AttributeError:
            return None

    def build(self, domains_spin, bounds_spin):
        """Build the scissors operator."""
        nsppol = self.nsppol

        if nsppol == 1:
            domains_spin = np.reshape(domains_spin, (1,-1,2))
            bounds_spin = np.reshape(bounds_spin, (1,-1,2))

        elif nsppol == 2:
            assert len(domains_spin) == nsppol
            assert len(bounds_spin) == nsppol
        else:
            raise ValueError("Wrong number of spins %d" % nsppol)

        # Construct the scissors operator for each spin.
        scissors_spin = nsppol * [None]
        for (spin, qps) in enumerate(self._qps_spin):
            domains = domains_spin[spin]
            bounds = bounds_spin[spin]
            print(domains)
            scissors = qps.build_scissors(domains, bounds=bounds, plot=False)

            scissors_spin[spin] = scissors

            # Save input so that we can reconstruct Scissors.
            self.domains_spin[spin] = domains
            self.bounds_spin[spin] = bounds

        self._scissors_spin = scissors_spin

    def plot_qpe_vs_e0(self, **kwargs):
        """Plot the quasiparticle corrections as function of the KS energy."""
        for (spin, qps) in enumerate(self._qps_spin):
            qps.plot_qps_vs_e0(with_fields="all", **kwargs)

    def plotfit(self):
        """Compare fit results with input data."""
        import matplotlib.pyplot as plt

        # TODO treat nsppol == 2
        assert self.nsppol == 1
        for spin in range(self.nsppol):
            scissors = self._scissors_spin[spin]
            qps = self._qps_spin[spin]
            e0mesh, qpcorrs = qps.get_e0mesh(), qps.get_qpeme0()

            plt.plot(e0mesh, qpcorrs, label="Input Data")
            intp_qpc = [scissors.apply(e0) for e0 in e0mesh]
            plt.plot(e0mesh, intp_qpc, label="Scissors(e)")
            plt.legend(loc="best")
            plt.show()

    def save_data(self, filepath, protocol=-1):
        """Save scissors parameters in a file. (Pickle format)"""
        assert all(s1 == s2 for s1, s2 in zip(self.domains_spin.keys(), self.bounds_spin.keys()))
        assert all(s1 == s2 for s1, s2 in zip(self.domains_spin.keys(), range(self.nsppol)))

        d = dict(
            qps_spin=self._qps_spin,
            domains_spin=[a.tolist() for a in self.domains_spin.values()],
            bounds_spin=[a.tolist() for a in self.bounds_spin.values()],
        )

        with open(filepath, "w") as fh:
            pickle.dump(d, fh, protocol=protocol)

    @classmethod
    def load_data(cls, filepath):
        """Load the scissors parameters from file (pickle format)."""
        with open(filepath, "r") as fh:
            d = AttrDict(pickle.load(fh))
            if cls._DEBUG:
                print("In load_data")
                print("domains_spin",d.domains_spin)
                print("bounds_spin",d.bounds_spin)

            new = cls(d.qps_spin)
            new.build(d.domains_spin, d.bounds_spin)
            return new

