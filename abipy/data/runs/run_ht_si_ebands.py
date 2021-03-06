#!/usr/bin/env python
"""Band structure of silicon with the HT interface."""
from __future__ import division, print_function

import sys
import os
import abipy.data as data  

from abipy import abilab
from pymatgen.io.abinitio.abiobjects import AbiStructure
from pymatgen.io.abinitio.calculations import bandstructure

from abipy.data.runs import enable_logging, AbipyTest, MixinTest


class HtSiEbandsFlowTest(AbipyTest, MixinTest):
    """
    Unit test for the flow defined in this module.  
    Users who just want to learn how to use this flow can ignore this section.
    """
    def setUp(self):
        super(HtSiEbandsFlowTest, self).setUp()
        self.init_dirs()
        self.flow = make_flow(self.workdir)

    # Remove all files except those matching these regular expression.
    #work[0].rename("out_WFK_0-etsf.nc", "si_scf_WFK-etsf.nc")
    #work[0].rename("out_DEN-etsf.nc", "si_DEN-etsf.nc")
    #work[0].rename("out_GSR.nc", "si_scf_GSR.nc")
                                                                                 
    #work[1].rename("out_GSR.nc", "si_nscf_GSR.nc")
                                                                                 
    #work.rmtree(exclude_wildcard="*.abin|*.about|*_WFK*|*_GSR.nc|*DEN-etsf.nc")


def make_flow(workdir="tmp_ht_si_ebands"):
    structure = AbiStructure.asabistructure(data.cif_file("si.cif"))

    scf_kppa = 40
    nscf_nband = 6
    ndivsm = 5
    #dos_ngkpt = [4,4,4]
    #dos_shiftk = [0.1, 0.2, 0.3]

    extra_abivars = dict(
        ecut=6, 
        timopt=-1,
        accesswff=3, 
        istwfk="*1",
    )

    manager = abilab.TaskManager.from_user_config()

    # Initialize the flow.
    # FIXME  Abistructure is not pickleable with protocol -1
    flow = abilab.AbinitFlow(workdir=workdir, manager=manager, pickle_protocol=0)

    work = bandstructure(structure, data.pseudos("14si.pspnc"), scf_kppa, nscf_nband, ndivsm, 
                         spin_mode="unpolarized", smearing=None, **extra_abivars)

    flow.register_work(work)
    return flow.allocate()

    #dos_kppa = 10
    #bands = bandstructure("hello_dos", runmode, structure, pseudos, scf_kppa, nscf_nband,
    #                      ndivsm, accuracy="normal", spin_mode="polarized",
    #                      smearing="fermi_dirac:0.1 eV", charge=0.0, scf_solver=None,
    #                      dos_kppa=dos_kppa)

@enable_logging
def main():
    flow = make_flow()
    return flow.build_and_pickle_dump()


if __name__ == "__main__":
    sys.exit(main())
