# -*- coding: utf-8 -*-
"""
Thermochemistry.test_references
Tests for Thermochemistry.references module
Created on Mon Jul 9 5:00:00 2018
"""
import unittest
import warnings
import numpy as np
from ase.build import molecule
from Thermochemistry import constants as c
from Thermochemistry.models.empirical import BaseThermo
from Thermochemistry.models.empirical.references import References
from Thermochemistry.models.statmech.idealgasthermo import IdealGasThermo

class TestReferences(unittest.TestCase):
	def setUp(self):
		unittest.TestCase.setUp(self)
		H2_thermo = BaseThermo(
			name = 'H2',
			phase = 'G',
			elements = {'H':2},
			thermo_model = IdealGasThermo,
			T_ref = c.T0('K'),
			HoRT_ref = 0.,
			vib_energies = np.array([4306.1793]) * c.c('cm/s') * c.h('eV s'),
			potentialenergy = -6.7598,
			geometry = 'linear',
			symmetrynumber = 2,
			spin = 0,
			atoms = molecule('H2'))

		H2O_thermo = BaseThermo(
			name = 'H2O',
			phase = 'G',
			elements = {'H': 2, 'O': 1},
			thermo_model = IdealGasThermo,
			T_ref = c.T0('K'),
			HoRT_ref = -241.826/(c.R('kJ/mol/K') * c.T0('K')),
			vib_energies = np.array([3825.434, 3710.264, 1582.432]) * c.c('cm/s') * c.h('eV s'),
			potentialenergy = -14.2209,
			geometry = 'nonlinear',
			symmetrynumber = 2,
			spin = 0,
			atoms = molecule('H2O'))

		O2_thermo = BaseThermo(
			name = 'H2O',
			phase = 'G',
			elements = {'O': 2},
			thermo_model = IdealGasThermo,
			T_ref = c.T0('K'),
			HoRT_ref = 0.,
			vib_energies = np.array([2205.]) * c.c('cm/s') * c.h('eV s'),
			potentialenergy = -9.86,
			geometry = 'linear',
			symmetrynumber = 2,
			spin = 1,
			atoms = molecule('O2'))
		self.references = References(references = [H2_thermo, H2O_thermo, O2_thermo])

	def test_get_elements(self):
		self.assertEqual(self.references.get_elements(), ('H', 'O'))

	def test_get_elements_matrix(self):
		elements_matrix = np.array([
			[2, 0],
			[2, 1],
			[0, 2]])
		np.testing.assert_array_equal(self.references.get_elements_matrix(), elements_matrix)

	def test_calc_offset(self):
		expected_element_offset = {'H': -123.10868373, 'O': -186.72503046}
		#print(self.references._references[0].thermo_model)
		self.references.calc_offset()
		calculated_element_offset = self.references.element_offset

		#Assess whether the keys are the same
		self.assertSetEqual(set(expected_element_offset.keys()), set(calculated_element_offset.keys()))
		#Assess whether the values assigned to the keys are the close
		for element in expected_element_offset.keys():
			self.assertAlmostEqual(expected_element_offset[element], calculated_element_offset[element])

	def test_get_specie_offset(self):
		self.references.calc_offset()
		elements = {'H': 2, 'O': 2}
		self.assertAlmostEqual(self.references.get_specie_offset(elements=elements), 619.667428373883)
		with self.assertWarns(RuntimeWarning):
			self.assertEqual(self.references.get_specie_offset(elements={'non-referenced element': 1}), 0.)


if __name__ == '__main__':
	unittest.main()