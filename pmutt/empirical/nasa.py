# -*- coding: utf-8 -*-
"""
pmutt.empirical.nasa

Operations related to Nasa polynomials
"""

import inspect
from copy import copy
from warnings import warn
import numpy as np
from scipy.optimize import minimize_scalar, minimize
from scipy.stats import variation
from pmutt import _is_iterable, _pass_expected_arguments, _apply_numpy_operation
from pmutt import constants as c
from pmutt.io.json import json_to_pmutt, remove_class
from pmutt.io.cantera import obj_to_CTI
from pmutt.empirical import EmpiricalBase
from pmutt.mixture import _get_mix_quantity

class Nasa(EmpiricalBase):
    """Stores the information for an individual species' NASA polynomial
    Inherits from :class:`~pmutt.empirical.EmpiricalBase`

    The thermodynamic properties are calculated using the following form:

    :math:`\\frac {Cp} {R} = a_{1} + a_{2} T + a_{3} T^{2} + a_{4} T^{3}
    + a_{5} T^{4}`

    :math:`\\frac {H} {RT} = a_{1} + a_{2} \\frac {T} {2} + a_{3}
    \\frac {T^{2}} {3} + a_{4} \\frac {T^{3}} {4} + a_{5}
    \\frac {T^{4}} {5} + a_{6} \\frac {1} {T}`

    :math:`\\frac {S} {R} = a_{1} \\ln {T} + a_{2} T + a_{3}
    \\frac {T^{2}} {2} + a_{4} \\frac {T^{3}} {3} + a_{5}
    \\frac {T^{4}} {4} + a_{7}`

    Attributes
    ----------
        T_low : float
            Lower temperature bound (in K)
        T_mid : float
            Middle temperature bound (in K)
        T_high : float
            High temperature bound (in K)
        a_low : (7,) `numpy.ndarray`_
            NASA polynomial to use between T_low and T_mid
        a_high : (7,) `numpy.ndarray`_
            NASA polynomial to use between T_mid and T_high
        cat_site : :class:`~pmutt.chemkin.CatSite` object, optional
            Catalyst site for adsorption. Used only for Chemkin input/output.
            Default is None
        n_sites : int, optional
            Number of catalyst sites occupied by species. If cat_site is not
            assigned, then n_sites is None. If cat_site is specified, the
            default is 1

    .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
    """
    def __init__(self, name, T_low, T_mid, T_high, a_low, a_high,
                 cat_site=None, n_sites=1, **kwargs):
        super().__init__(name=name, **kwargs)
        self.T_low = T_low
        self.T_mid = T_mid
        self.T_high = T_high
        self.a_low = np.array(a_low)
        self.a_high = np.array(a_high)
        if inspect.isclass(cat_site):
            self.cat_site = _pass_expected_arguments(cat_site, **kwargs)
        else:
            self.cat_site = cat_site
        if self.cat_site is None:
            n_sites = None
        self.n_sites = n_sites

    def get_a(self, T):
        """Returns the correct polynomial range based on T_low, T_mid and
        T_high

        Parameters
        ----------
            T : float
                Temperature in K
        Returns
        -------
            a : (7,) `numpy.ndarray`_
                NASA polynomial coefficients

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        if type(self.T_mid) is list:
            self.T_mid = self.T_mid[0]
        if T < self.T_mid:
            if T < self.T_low:
                warn('Temperature below T_low for {}'.format(self.name),
                     RuntimeWarning)
            return self.a_low
        else:
            if T > self.T_high:
                warn('Temperature above T_high for {}'.format(self.name),
                     RuntimeWarning)
            return self.a_high

    def get_CpoR(self, T, raise_error=True, raise_warning=True, **kwargs):
        """Calculate the dimensionless heat capacity

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
            raise_error : bool, optional
                If True, raises an error if any of the modes do not have the
                quantity of interest. Default is True
            raise_warning : bool, optional
                Only relevant if raise_error is False. Raises a warning if any
                of the modes do not have the quantity of interest. Default is
                True
            kwargs : key-word arguments
                Arguments to calculate mixture model properties, if any
        Returns
        -------
            CpoR : float or (N,) `numpy.ndarray`_
                Dimensionless heat capacity

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        if _is_iterable(T):
            CpoR = np.zeros(len(T))
            for i, T_i in enumerate(T):
                a = self.get_a(T_i)
                CpoR[i] = get_nasa_CpoR(a=a, T=T_i) \
                    + np.sum(_get_mix_quantity(self.misc_models,
                                               method_name='get_CpoR',
                                               raise_error=raise_error,
                                               raise_warning=raise_warning,
                                               default_value=0.,
                                               T=T_i, **kwargs))
        else:
            a = self.get_a(T=T)
            CpoR = get_nasa_CpoR(a=a, T=T) \
                + np.sum(_get_mix_quantity(self.misc_models, 
                                           method_name='get_CpoR',
                                           raise_error=raise_error,
                                           raise_warning=raise_warning,
                                           default_value=0.,
                                           T=T, **kwargs))
        return CpoR

    def get_Cp(self, T, units, raise_error=True, raise_warning=True, **kwargs):
        """Calculate the heat capacity

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
            units : str
                Units as string. See :func:`~pmutt.constants.R` for accepted
                units.
            raise_error : bool, optional
                If True, raises an error if any of the modes do not have the
                quantity of interest. Default is True
            raise_warning : bool, optional
                Only relevant if raise_error is False. Raises a warning if any
                of the modes do not have the quantity of interest. Default is
                True
            kwargs : key-word arguments
                Arguments to calculate mixture model properties, if any
        Returns
        -------
            Cp : float or (N,) `numpy.ndarray`_
                Heat capacity

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        return self.get_CpoR(T=T)*c.R(units)

    def get_HoRT(self, T, raise_error=True, raise_warning=True, **kwargs):
        """Calculate the dimensionless enthalpy

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
            raise_error : bool, optional
                If True, raises an error if any of the modes do not have the
                quantity of interest. Default is True
            raise_warning : bool, optional
                Only relevant if raise_error is False. Raises a warning if any
                of the modes do not have the quantity of interest. Default is
                True
            kwargs : key-word arguments
                Arguments to calculate mixture model properties, if any
        Returns
        -------
            HoRT : float or (N,) `numpy.ndarray`_
                Dimensionless enthalpy

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        if _is_iterable(T):
            HoRT = np.zeros_like(T)
            for i, T_i in enumerate(T):
                a = self.get_a(T=T_i)
                HoRT[i] = get_nasa_HoRT(a=a, T=T_i) \
                    + np.sum(_get_mix_quantity(misc_models=self.misc_models,
                                               method_name='get_HoRT',
                                               raise_error=raise_error,
                                               raise_warning=raise_warning,
                                               default_value=0.,
                                               T=T_i, **kwargs))
        else:
            a = self.get_a(T=T)
            HoRT = get_nasa_HoRT(a=a, T=T) \
                + np.sum(_get_mix_quantity(misc_models=self.misc_models,
                                           method_name='get_HoRT',
                                           raise_error=raise_error,
                                           raise_warning=raise_warning,
                                           default_value=0.,
                                           T=T, **kwargs))
        return HoRT

    def get_H(self, T, units, raise_error=True, raise_warning=True, **kwargs):
        """Calculate the enthalpy

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
            units : str
                Units as string. See :func:`~pmutt.constants.R` for accepted
                units but omit the '/K' (e.g. J/mol).
            raise_error : bool, optional
                If True, raises an error if any of the modes do not have the
                quantity of interest. Default is True
            raise_warning : bool, optional
                Only relevant if raise_error is False. Raises a warning if any
                of the modes do not have the quantity of interest. Default is
                True
            kwargs : key-word arguments
                Arguments to calculate mixture model properties, if any
        Returns
        -------
            H : float or (N,) `numpy.ndarray`_
                Enthalpy

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        return self.get_HoRT(T=T, raise_error=raise_error,
                             raise_warning=raise_warning, **kwargs) \
               *T*c.R('{}/K'.format(units))

    def get_SoR(self, T, raise_error=True, raise_warning=True, **kwargs):
        """Calculate the dimensionless entropy

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
            raise_error : bool, optional
                If True, raises an error if any of the modes do not have the
                quantity of interest. Default is True
            raise_warning : bool, optional
                Only relevant if raise_error is False. Raises a warning if any
                of the modes do not have the quantity of interest. Default is
                True
            kwargs : key-word arguments
                Arguments to calculate mixture model properties, if any
        Returns
        -------
            SoR : float or (N,) `numpy.ndarray`_
                Dimensionless entropy

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        if _is_iterable(T):
            SoR = np.zeros_like(T)
            for i, T_i in enumerate(T):
                a = self.get_a(T=T_i)
                SoR[i] = get_nasa_SoR(a=a, T=T_i) \
                    + np.sum(_get_mix_quantity(misc_models=self.misc_models,
                                               method_name='get_SoR',
                                               raise_error=raise_error,
                                               raise_warning=raise_warning,
                                               default_value=0.,
                                               T=T_i, **kwargs))
        else:
            a = self.get_a(T=T)
            SoR = get_nasa_SoR(a=a, T=T) \
                + np.sum(_get_mix_quantity(misc_models=self.misc_models,
                                           method_name='get_SoR',
                                           raise_error=raise_error,
                                           raise_warning=raise_warning,
                                           default_value=0.,
                                           T=T, **kwargs))
        return SoR

    def get_S(self, T, units, raise_error=True, raise_warning=True, **kwargs):
        """Calculate the entropy

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
            units : str
                Units as string. See :func:`~pmutt.constants.R` for accepted
                units.
            raise_error : bool, optional
                If True, raises an error if any of the modes do not have the
                quantity of interest. Default is True
            raise_warning : bool, optional
                Only relevant if raise_error is False. Raises a warning if any
                of the modes do not have the quantity of interest. Default is
                True
            kwargs : key-word arguments
                Arguments to calculate mixture model properties, if any
        Returns
        -------
            S : float or (N,) `numpy.ndarray`_
                Entropy

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        return self.get_SoR(T=T, raise_error=raise_error,
                            raise_warning=raise_warning, **kwargs)*c.R(units)

    def get_GoRT(self, T, raise_error=True, raise_warning=True, **kwargs):
        """Calculate the dimensionless Gibbs free energy

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
            raise_error : bool, optional
                If True, raises an error if any of the modes do not have the
                quantity of interest. Default is True
            raise_warning : bool, optional
                Only relevant if raise_error is False. Raises a warning if any
                of the modes do not have the quantity of interest. Default is
                True
            kwargs : key-word arguments
                Arguments to calculate mixture model properties, if any
        Returns
        -------
            GoRT : float or (N,) `numpy.ndarray`_
                Dimensionless Gibbs free energy

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        GoRT = self.get_HoRT(T, raise_error=raise_error,
                             raise_warning=raise_warning, **kwargs) \
               - self.get_SoR(T, raise_error=raise_error,
                              raise_warning=raise_warning, **kwargs)
        return GoRT

    def get_G(self, T, units, raise_error=True, raise_warning=True, **kwargs):
        """Calculate the Gibbs energy

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
            units : str
                Units as string. See :func:`~pmutt.constants.R` for accepted
                units but omit the '/K' (e.g. J/mol).
            raise_error : bool, optional
                If True, raises an error if any of the modes do not have the
                quantity of interest. Default is True
            raise_warning : bool, optional
                Only relevant if raise_error is False. Raises a warning if any
                of the modes do not have the quantity of interest. Default is
                True
            kwargs : key-word arguments
                Arguments to calculate mixture model properties, if any
        Returns
        -------
            G : float or (N,) `numpy.ndarray`_
                Gibbs energy

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        return self.get_GoRT(T=T, raise_error=raise_error,
                             raise_warning=raise_warning, **kwargs) \
            * T*c.R('{}/K'.format(units))

    @classmethod
    def from_data(cls, name, T, CpoR, T_ref, HoRT_ref, SoR_ref, elements=None,
                  T_mid=None, **kwargs):
        """Calculates the NASA polynomials using thermodynamic data

        Parameters
        ----------
            name : str
                Name of the species
            T : (N,) `numpy.ndarray`_
                Temperatures in K used for fitting CpoR.
            CpoR : (N,) `numpy.ndarray`_
                Dimensionless heat capacity corresponding to T.
            T_ref : float
                Reference temperature in K used fitting empirical coefficients.
            HoRT_ref : float
                Dimensionless reference enthalpy that corresponds to T_ref.
            SoR_ref : float
                Dimensionless entropy that corresponds to T_ref.
            elements : dict
                Composition of the species.
                Keys of dictionary are elements, values are stoichiometric
                values in a formula unit.
                e.g. CH3OH can be represented as:
                {'C': 1, 'H': 4, 'O': 1,}.
            T_mid : float or iterable of float, optional
                Guess for T_mid. If float, only uses that value for T_mid. If
                list, finds the best fit for each element in the list. If None,
                a range of T_mid values are screened between the 6th lowest
                and 6th highest value of T.
        Returns
        -------
            Nasa : Nasa object
                Nasa object with polynomial terms fitted to data.

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        T_low = min(T)
        T_high = max(T)

        # Find midpoint temperature, and a[0] through a[4] parameters
        a_low, a_high, T_mid_out = _fit_CpoR(T=T, CpoR=CpoR, T_mid=T_mid)
        # Fit a[5] parameter using reference enthalpy
        a_low[5], a_high[5] = _fit_HoRT(T_ref=T_ref, HoRT_ref=HoRT_ref,
                                        a_low=a_low, a_high=a_high,
                                        T_mid=T_mid_out)
        # Fit a[6] parameter using reference entropy
        a_low[6], a_high[6] = _fit_SoR(T_ref=T_ref, SoR_ref=SoR_ref,
                                       a_low=a_low, a_high=a_high,
                                       T_mid=T_mid_out)
        return cls(name=name, T_low=T_low, T_high=T_high, T_mid=T_mid_out,
                   a_low=a_low, a_high=a_high, elements=elements, **kwargs)

    @classmethod
    def from_statmech(cls, name, statmech_model, T_low, T_high, T_mid=None,
                      references=None, elements=None, **kwargs):
        """Calculates the NASA polynomials using statistical mechanic models

        Parameters
        ----------
            name : str
                Name of the species
            statmech_model : `pmutt.statmech.StatMech` object or class
                Statistical Mechanics model to generate data
            T_low : float
                Lower limit temerature in K
            T_high : float
                Higher limit temperature in K
            T_mid : float or iterable of float, optional
                Guess for T_mid. If float, only uses that value for T_mid. If
                list, finds the best fit for each element in the list. If None,
                a range of T_mid values are screened between the 6th lowest
                and 6th highest value of T.
            references : `pmutt.empirical.references.References` object
                Reference to adjust enthalpy
            elements : dict
                Composition of the species.
                Keys of dictionary are elements, values are stoichiometric
                values in a formula unit.
                e.g. CH3OH can be represented as:
                {'C': 1, 'H': 4, 'O': 1,}.
            kwargs : keyword arguments
                Used to initalize ``statmech_model`` or ``EmpiricalBase``
                attributes to be stored.
        Returns
        -------
            Nasa : Nasa object
                Nasa object with polynomial terms fitted to data.
        """
        # Initialize the StatMech object
        if inspect.isclass(statmech_model):
            statmech_model = statmech_model(name=name, references=references,
                                            elements=elements, **kwargs)

        # Generate heat capacity data
        T = np.linspace(T_low, T_high)
        if T_mid is not None:
            # Check to see if specified T_mid's are in T and, if not,
            # insert them into T.
            # If a single value for T_mid is chosen, convert to a tuple
            if not _is_iterable(T_mid):
                T_mid = (T_mid,)
            for x in range(0, len(T_mid)):
                if np.where(T == T_mid[x])[0].size == 0:
                    # Insert T_mid's into T and save position
                    Ts_index = np.where(T > T_mid[x])[0][0]
                    T = np.insert(T, Ts_index, T_mid[x])
        CpoR = np.array(
            [statmech_model.get_CpoR(T=T_i, use_references=True) for T_i in T])
        # Generate enthalpy and entropy data
        T_ref = c.T0('K')
        HoRT_ref = statmech_model.get_HoRT(T=T_ref, use_references=True)
        SoR_ref = statmech_model.get_SoR(T=T_ref, use_references=True)

        return cls.from_data(name=name, T=T, CpoR=CpoR, T_ref=T_ref,
                             HoRT_ref=HoRT_ref, SoR_ref=SoR_ref, T_mid=T_mid,
                             statmech_model=statmech_model, elements=elements,
                             references=references, **kwargs)

    @classmethod
    def from_model(cls, name, model, T_low, T_high, elements=None, **kwargs):
        """Calculates the NASA polynomials using statistical mechanic models

        Parameters
        ----------
            name : str
                Name of the species
            model : Model object or class
                Model to generate data. Must contain the methods `get_CpoR`,
                `get_HoRT` and `get_SoR`
            T_low : float
                Lower limit temerature in K
            T_high : float
                Higher limit temperature in K
            elements : dict
                Composition of the species.
                Keys of dictionary are elements, values are stoichiometric
                values in a formula unit.
                e.g. CH3OH can be represented as:
                {'C': 1, 'H': 4, 'O': 1,}.
            kwargs : keyword arguments
                Used to initalize model if a class is passed.
        Returns
        -------
            Nasa : Nasa object
                Nasa object with polynomial terms fitted to data.
        """
        # Initialize the StatMech object
        if inspect.isclass(model):
            model = model(name=name, elements=elements, **kwargs)

        # Optimize T_mid
        T = np.linspace(T_low, T_high, num=20.)
        # CpoR = np.array([model.get_CpoR(T=T_i) for T_i in T])
        # res = minimize_scalar(fun=_get_T_mid_nasa1, method='bounded', 
        #                args=(T, CpoR), bounds=(T_low, T_high))
        res = minimize_scalar(fun=_get_T_mid_nasa, method='bounded', 
                       args=(T_low, T_high, model), bounds=(T_low, T_high))
        T_mid = res.x
        CpoR = [model.get_CpoR(T=T_i) for T_i in T]

        # Generate enthalpy and entropy data
        HoRT_ref = model.get_HoRT(T=T_mid)
        SoR_ref = model.get_SoR(T=T_mid)

        return cls.from_data(name=name, T=T, CpoR=CpoR, T_ref=T_mid,
                             HoRT_ref=HoRT_ref, SoR_ref=SoR_ref, T_mid=T_mid,
                             statmech_model=model, elements=elements,
                             **kwargs)

    def to_CTI(self):
        elements = {key: int(val) for key, val in self.elements.items()}
        cti_str = ('species(name="{}", atoms={},\n'
                   '        thermo=(NASA([{}, {}],\n'
                   '                     [{: 2.8E}, {: 2.8E}, {: 2.8E},\n'
                   '                      {: 2.8E}, {: 2.8E}, {: 2.8E},\n'
                   '                      {: 2.8E}]),\n'
                   '                NASA([{}, {}], \n'
                   '                     [{: 2.8E}, {: 2.8E}, {: 2.8E},\n'
                   '                      {: 2.8E}, {: 2.8E}, {: 2.8E},\n'
                   '                      {: 2.8E}])))\n').format(
                            self.name, obj_to_CTI(elements), self.T_low,
                            self.T_mid, self.a_low[0], self.a_low[1],
                            self.a_low[2], self.a_low[3], self.a_low[4],
                            self.a_low[5], self.a_low[6], self.T_mid,
                            self.T_high, self.a_high[0], self.a_high[1],
                            self.a_high[2], self.a_high[3], self.a_high[4],
                            self.a_high[5], self.a_high[6])
        return cti_str

    def to_dict(self):
        """Represents object as dictionary with JSON-accepted datatypes

        Returns
        -------
            obj_dict : dict
        """
        obj_dict = super().to_dict()
        obj_dict['class'] = str(self.__class__)
        obj_dict['type'] = 'nasa'
        obj_dict['a_low'] = list(self.a_low)
        obj_dict['a_high'] = list(self.a_high)
        obj_dict['T_low'] = self.T_low
        obj_dict['T_mid'] = self.T_mid
        obj_dict['T_high'] = self.T_high
        try:
            obj_dict['cat_site'] = self.cat_site.to_dict()
        except AttributeError:
            obj_dict['cat_site'] = None
        obj_dict['n_sites'] = self.n_sites
        return obj_dict

    @classmethod
    def from_dict(cls, json_obj):
        """Recreate an object from the JSON representation.

        Parameters
        ----------
            json_obj : dict
                JSON representation
        Returns
        -------
            Nasa : Nasa object
        """
        json_obj = remove_class(json_obj)
        # Reconstruct statmech model
        json_obj['statmech_model'] = json_to_pmutt(json_obj['statmech_model'])
        json_obj['cat_site'] = json_to_pmutt(json_obj['cat_site'])
        json_obj['misc_models'] = json_to_pmutt(json_obj['misc_models'])
        return cls(**json_obj)

class Nasa9(EmpiricalBase):
    """Stores the NASA9 polynomials for species.
    Inherits from :class:`~pmutt.empirical.EmpiricalBase`

    :math:`\\frac {Cp} {R} = a_{1} T^{-2} + a_{2} T^{-1} + a_{3} + a_{4} T
    + a_{5} T^{2} + a_{6} T^{3} + a_{7} T^{4}`

    :math:`\\frac {H} {RT} = -a_{1} \\frac {T^{-2}} {2} +
    a_{2} \\frac {ln {T}} {T} + a_{3} + a_{4} \\frac {T} {2} + a_{5}
    \\frac {T^{2}} {3} + a_{6} \\frac {T^{3}} {4} + a_{7} \\frac {T^{4}} {5} +
    a_{8} \\frac {1} {T}`

    :math:`\\frac {S} {R} = -a_{1}\\frac {T^{-2}} {2} - a_2 \\frac {1} {T} +
    a_{3} \\ln {T} + a_{4} T + a_{5} \\frac {T^{2}} {2} + a_{6}
    \\frac {T^{3}} {3} + a_{7}\\frac {T^{4}} {4} + a_{8}`

    Attributes
    ----------
        nasas : list of :class:`~pmutt.empirical.nasa.SingleNasa9`
            NASA9 polynomials for each temperature interval
        T_low : float
            Lower temperature bound (in K). Determined from inputted `nasas`
        T_high : float
            High temperature bound (in K). Determined from inputted `nasas`
    """
    def __init__(self, name, nasas, n_sites=1, **kwargs):
        super().__init__(name=name, **kwargs)
        self.n_sites = n_sites
        self.nasas = nasas

    def __iter__(self):
        for nasa in self.nasas:
            yield nasa

    def __getitem__(self, key):
        return self.nasas[key]

    def __len__(self):
        return len(self.nasas)

    @property
    def nasas(self):
        return self._nasas

    @nasas.setter
    def nasas(self, val):
        self._nasas = copy(val)
        self.T_low = self._get_T_limit(limit='min')
        self.T_high = self._get_T_limit(limit='max')

    def _get_nasa(self, T):
        """Gets the relevant :class:`~pmutt.empirical.nasa.SingleNasa9` object
        given a temperature

        Attributes
        ----------
            T : float
                Temperature in float
        Returns
        -------
            nasa : :class:`~pmutt.empirical.nasa.SingleNasa9` object
                Relevant NASA9 polynomial for T
        Raises
        ------
            ValueError:
                Raised if no valid :class:`~pmutt.empirical.nasa.SingleNasa9`
                exists for T
        """
        for nasa in self.nasas:
            if T <= nasa.T_high and T >= nasa.T_low:
                return nasa
        else:
            raise ValueError('No valid SingleNasa9 object for T: {}'.format(T))

    def get_CpoR(self, T, raise_error=True, raise_warning=True, **kwargs):
        """Calculate the dimensionless heat capacity

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
            raise_error : bool, optional
                If True, raises an error if any of the modes do not have the
                quantity of interest. Default is True
            raise_warning : bool, optional
                Only relevant if raise_error is False. Raises a warning if any
                of the modes do not have the quantity of interest. Default is
                True
            kwargs : key-word arguments
                Arguments to calculate mixture model properties, if any
        Returns
        -------
            CpoR : float or (N,) `numpy.ndarray`_
                Dimensionless heat capacity

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        if _is_iterable(T):
            CpoR = np.zeros(len(T))
            for i, T_i in enumerate(T):
                nasa = self._get_nasa(T_i)
                CpoR[i] = nasa.get_CpoR(T=T_i) \
                          + np.sum(_get_mix_quantity(self.misc_models,
                                                     method_name='get_CpoR',
                                                     raise_error=raise_error,
                                                     raise_warning=raise_warning,
                                                     default_value=0.,
                                                     T=T_i, **kwargs))
        else:
            nasa = self._get_nasa(T=T)
            CpoR = nasa.get_CpoR(T=T) \
                   + np.sum(_get_mix_quantity(self.misc_models, 
                                              method_name='get_CpoR',
                                              raise_error=raise_error,
                                              raise_warning=raise_warning,
                                              default_value=0.,
                                              T=T, **kwargs))
        if len(CpoR) == 1:
            CpoR = CpoR.item(0)
        return CpoR

    def get_Cp(self, T, units, raise_error=True, raise_warning=True, **kwargs):
        """Calculate the heat capacity

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
            units : str
                Units as string. See :func:`~pmutt.constants.R` for accepted
                units.
            raise_error : bool, optional
                If True, raises an error if any of the modes do not have the
                quantity of interest. Default is True
            raise_warning : bool, optional
                Only relevant if raise_error is False. Raises a warning if any
                of the modes do not have the quantity of interest. Default is
                True
            kwargs : key-word arguments
                Arguments to calculate mixture model properties, if any
        Returns
        -------
            Cp : float or (N,) `numpy.ndarray`_
                Heat capacity

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        return self.get_CpoR(T=T)*c.R(units)

    def get_HoRT(self, T, raise_error=True, raise_warning=True, **kwargs):
        """Calculate the dimensionless enthalpy

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
            raise_error : bool, optional
                If True, raises an error if any of the modes do not have the
                quantity of interest. Default is True
            raise_warning : bool, optional
                Only relevant if raise_error is False. Raises a warning if any
                of the modes do not have the quantity of interest. Default is
                True
            kwargs : key-word arguments
                Arguments to calculate mixture model properties, if any
        Returns
        -------
            HoRT : float or (N,) `numpy.ndarray`_
                Dimensionless enthalpy

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        if _is_iterable(T):
            HoRT = np.zeros_like(T)
            for i, T_i in enumerate(T):
                nasa = self._get_nasa(T=T_i)
                HoRT[i] = nasa.get_HoRT(T=T_i) \
                          + np.sum(_get_mix_quantity(
                                        misc_models=self.misc_models,
                                        method_name='get_HoRT',
                                        raise_error=raise_error,
                                        raise_warning=raise_warning,
                                        default_value=0.,
                                        T=T_i, **kwargs))
        else:
            nasa = self._get_nasa(T=T)
            HoRT = nasa.get_HoRT(T=T) \
                   + np.sum(_get_mix_quantity(misc_models=self.misc_models,
                                              method_name='get_HoRT',
                                              raise_error=raise_error,
                                              raise_warning=raise_warning,
                                              default_value=0.,
                                              T=T, **kwargs))
        if len(HoRT) == 1:
            HoRT = HoRT.item(0)
        return HoRT

    def get_H(self, T, units, raise_error=True, raise_warning=True, **kwargs):
        """Calculate the enthalpy

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
            units : str
                Units as string. See :func:`~pmutt.constants.R` for accepted
                units but omit the '/K' (e.g. J/mol).
            raise_error : bool, optional
                If True, raises an error if any of the modes do not have the
                quantity of interest. Default is True
            raise_warning : bool, optional
                Only relevant if raise_error is False. Raises a warning if any
                of the modes do not have the quantity of interest. Default is
                True
            kwargs : key-word arguments
                Arguments to calculate mixture model properties, if any
        Returns
        -------
            H : float or (N,) `numpy.ndarray`_
                Enthalpy

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        return self.get_HoRT(T=T, raise_error=raise_error,
                             raise_warning=raise_warning, **kwargs) \
               *T*c.R('{}/K'.format(units))

    def get_SoR(self, T, raise_error=True, raise_warning=True, **kwargs):
        """Calculate the dimensionless entropy

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
            raise_error : bool, optional
                If True, raises an error if any of the modes do not have the
                quantity of interest. Default is True
            raise_warning : bool, optional
                Only relevant if raise_error is False. Raises a warning if any
                of the modes do not have the quantity of interest. Default is
                True
            kwargs : key-word arguments
                Arguments to calculate mixture model properties, if any
        Returns
        -------
            SoR : float or (N,) `numpy.ndarray`_
                Dimensionless entropy

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        if _is_iterable(T):
            SoR = np.zeros_like(T)
            for i, T_i in enumerate(T):
                nasa = self._get_nasa(T=T_i)
                SoR[i] = nasa.get_SoR(T=T_i) \
                         + np.sum(_get_mix_quantity(
                                        misc_models=self.misc_models,
                                        method_name='get_SoR',
                                        raise_error=raise_error,
                                        raise_warning=raise_warning,
                                        default_value=0.,
                                        T=T_i, **kwargs))
        else:
            nasa = self._get_nasa(T=T)
            SoR = nasa.get_SoR(T=T) \
                  + np.sum(_get_mix_quantity(misc_models=self.misc_models,
                                             method_name='get_SoR',
                                             raise_error=raise_error,
                                             raise_warning=raise_warning,
                                             default_value=0.,
                                             T=T, **kwargs))
        if len(SoR) == 1:
            SoR = SoR.item(0)
        return SoR

    def get_S(self, T, units, raise_error=True, raise_warning=True, **kwargs):
        """Calculate the entropy

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
            units : str
                Units as string. See :func:`~pmutt.constants.R` for accepted
                units.
            raise_error : bool, optional
                If True, raises an error if any of the modes do not have the
                quantity of interest. Default is True
            raise_warning : bool, optional
                Only relevant if raise_error is False. Raises a warning if any
                of the modes do not have the quantity of interest. Default is
                True
            kwargs : key-word arguments
                Arguments to calculate mixture model properties, if any
        Returns
        -------
            S : float or (N,) `numpy.ndarray`_
                Entropy

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        return self.get_SoR(T=T, raise_error=raise_error,
                            raise_warning=raise_warning, **kwargs)*c.R(units)

    def get_GoRT(self, T, raise_error=True, raise_warning=True, **kwargs):
        """Calculate the dimensionless Gibbs free energy

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
            raise_error : bool, optional
                If True, raises an error if any of the modes do not have the
                quantity of interest. Default is True
            raise_warning : bool, optional
                Only relevant if raise_error is False. Raises a warning if any
                of the modes do not have the quantity of interest. Default is
                True
            kwargs : key-word arguments
                Arguments to calculate mixture model properties, if any
        Returns
        -------
            GoRT : float or (N,) `numpy.ndarray`_
                Dimensionless Gibbs free energy

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        GoRT = self.get_HoRT(T, raise_error=raise_error,
                             raise_warning=raise_warning, **kwargs) \
               - self.get_SoR(T, raise_error=raise_error,
                              raise_warning=raise_warning, **kwargs)
        return GoRT

    def get_G(self, T, units, raise_error=True, raise_warning=True, **kwargs):
        """Calculate the Gibbs energy

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
            units : str
                Units as string. See :func:`~pmutt.constants.R` for accepted
                units but omit the '/K' (e.g. J/mol).
            raise_error : bool, optional
                If True, raises an error if any of the modes do not have the
                quantity of interest. Default is True
            raise_warning : bool, optional
                Only relevant if raise_error is False. Raises a warning if any
                of the modes do not have the quantity of interest. Default is
                True
            kwargs : key-word arguments
                Arguments to calculate mixture model properties, if any
        Returns
        -------
            G : float or (N,) `numpy.ndarray`_
                Gibbs energy

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        return self.get_GoRT(T=T, raise_error=raise_error,
                             raise_warning=raise_warning, **kwargs) \
            * T*c.R('{}/K'.format(units))

    @classmethod
    def from_data(cls, name, T, CpoR, T_ref, HoRT_ref, SoR_ref, elements=None,
                  T_mid=None, fit_T_mid=True, **kwargs):
        """Calculates the NASA polynomials using thermodynamic data

        Parameters
        ----------
            name : str
                Name of the species
            T : (N,) `numpy.ndarray`_
                Temperatures in K used for fitting CpoR.
            CpoR : (N,) `numpy.ndarray`_
                Dimensionless heat capacity corresponding to T.
            T_ref : float
                Reference temperature in K used fitting empirical coefficients.
            HoRT_ref : float
                Dimensionless reference enthalpy that corresponds to T_ref.
            SoR_ref : float
                Dimensionless entropy that corresponds to T_ref.
            elements : dict
                Composition of the species.
                Keys of dictionary are elements, values are stoichiometric
                values in a formula unit.
                e.g. CH3OH can be represented as:
                {'C': 1, 'H': 4, 'O': 1,}.
            T_mid : iterable of float, optional
                Guess for T_mid. If float, only uses that value for T_mid. If
                list, finds the best fit for each element in the list. If None,
                a range of T_mid values are screened between the 6th lowest
                and 6th highest value of T.
        Returns
        -------
            Nasa : Nasa object
                Nasa object with polynomial terms fitted to data.

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        T_low = min(T)
        T_high = max(T)

        # Find midpoint temperature, and a[0] through a[4] parameters
        a = _fit_CpoR9(T=T, CpoR=CpoR, T_low=T_low, T_high=T_high, T_mid=T_mid)
        # Fit a[7] parameter using reference enthalpy
        a = _fit_HoRT9(T_ref=T_ref, HoRT_ref=HoRT_ref, a=a, T_mid=T_mid)
        # Fit a[8] parameter using reference entropy
        a = _fit_SoR9(T_ref=T_ref, SoR_ref=SoR_ref, a=a, T_mid=T_mid)

        nasas = []
        T_interval = np.concatenate([[T_low], T_mid, [T_high]])
        for a_row, T_low, T_high in zip(a, T_interval, T_interval[1:]):
            nasas.append(SingleNasa9(T_low=T_low, T_high=T_high, a=a_row))

        return cls(name=name, nasas=nasas, elements=elements, **kwargs)


    @classmethod
    def from_model(cls, name, model, T_low, T_high, elements=None, T_mid=None,
                   n_interval=2, n_T=50, fit_T_mid=True, **kwargs):
        """Calculates the NASA polynomials using statistical mechanic models

        Parameters
        ----------
            name : str
                Name of the species
            model : Model object or class
                Model to generate data. Must contain the methods `get_CpoR`,
                `get_HoRT` and `get_SoR`
            T_low : float
                Lower limit temerature in K
            T_high : float
                Higher limit temperature in K
            elements : dict
                Composition of the species.
                Keys of dictionary are elements, values are stoichiometric
                values in a formula unit.
                e.g. CH3OH can be represented as:
                {'C': 1, 'H': 4, 'O': 1,}.
            T_mid : (n_interval,) nd.ndarray
                Temperatures (in K) to use at intervals. See `fit_T_mid` for
                behavior.
            n_interval : int, optional
                Number of NASA9 polynomials to create. Default is 2
            n_T : int, optional
                Number of temperature values to evaluate between each interval.
                Larger values result is a better fit but take longer to run.
                Default is 50.
            fit_T_mid : bool, optional
                If True, T_mid values initial values and can be changed. If
                False, T_mid values are not changed
            kwargs : keyword arguments
                Used to initalize model if a class is passed.
        Returns
        -------
            Nasa9 : Nasa9 object
                Nasa object with polynomial terms fitted to data.
        """
        # Initialize the model object
        if inspect.isclass(model):
            model = model(name=name, elements=elements, **kwargs)

        # Optimize T_mids
        if fit_T_mid:
            # If guesses not specified, use even spacing
            if T_mid is None:
                T_mid0 = np.linspace(T_low, T_high, n_interval+1)[1:-1]
            else:
                T_mid0 = T_mid
            res = minimize(method='Nelder-Mead', x0=T_mid0,
                           fun=_calc_T_mid_mse_nasa9,
                           args=(T_low, T_high, model, n_T))
            T_mid = res.x

        # Generate heat capacity data for from_data
        T_interval = np.concatenate([[T_low], T_mid, [T_high]])
        for i, (T1, T2) in enumerate(zip(T_interval, T_interval[1:])):
            if i == 0:
                T = np.linspace(T1, T2, n_T)
            else:
                T = np.concatenate([T, np.linspace(T1, T2, n_T)])
        CpoR = np.array([model.get_CpoR(T=T_i) for T_i in T])

        # Generate enthalpy and entropy data
        HoRT_ref = model.get_HoRT(T=T_low)
        SoR_ref = model.get_SoR(T=T_low)

        return cls.from_data(name=name, T=T, CpoR=CpoR, T_ref=T_low,
                             HoRT_ref=HoRT_ref, SoR_ref=SoR_ref, T_mid=T_mid,
                             model=model, elements=elements, fit_T_mid=False,
                             **kwargs)

    def _get_T_limit(self, limit):
        """Calculates the global `T_low` or `T_high` value from the inputted
        NASA9 polynomials.

        Parameters
        ----------
            limit : str
                Limit to assess. 'min' returns the global `T_low` and 'max'
                returns the global `T_high`
        Raises
        ------
            ValueError
                Raised if limit is not supported.

        """
        # Assign the relevant attribute based on limit
        if limit == 'min':
            T_attr = 'T_low'
        elif limit == 'max':
            T_attr = 'T_high'
        else:
            raise ValueError('Unsupported value for limit: {}. The only '
                             'supported values are "min" and '
                             '"max"'.format(limit))
        # Gather the values from the NASA9 polynomials
        T_lim = [getattr(nasa, T_attr) for nasa in self._nasas]
        return _apply_numpy_operation(quantity=T_lim, operation=limit)

    def to_dict(self):
        """Represents object as dictionary with JSON-accepted datatypes

        Returns
        -------
            obj_dict : dict
        """
        obj_dict = super().to_dict()
        obj_dict['class'] = str(self.__class__)
        obj_dict['type'] = 'nasa9'
        obj_dict['nasa'] = [nasa.to_dict() for nasa in self.nasas]
        obj_dict['n_sites'] = self.n_sites
        return obj_dict

    @classmethod
    def from_dict(cls, json_obj):
        """Recreate an object from the JSON representation.

        Parameters
        ----------
            json_obj : dict
                JSON representation
        Returns
        -------
            Nasa : Nasa object
        """
        json_obj = remove_class(json_obj)
        # Reconstruct statmech model
        json_obj['nasas'] = [json_to_pmutt(nasa) for nasa in json_obj['nasas']]
        json_obj['statmech_model'] = json_to_pmutt(json_obj['statmech_model'])
        json_obj['misc_models'] = json_to_pmutt(json_obj['misc_models'])
        return cls(**json_obj)

    def to_CTI(self):
        elements = {key: int(val) for key, val in self.elements.items()}
        cti_str = ('species(name="{}", atoms={},\n'
                   '        thermo=(').format(
                            self.name, obj_to_CTI(elements))
        for i, nasa in enumerate(self.nasas):
            line_indent = (i != 0)
            cti_str += '{},\n'.format(nasa.to_CTI(line_indent=line_indent))
        cti_str = '{})\n'.format(cti_str[:-2])
        return cti_str


class SingleNasa9(EmpiricalBase):
    """Stores the NASA9 polynomial for a defined interval.
    Inherits from :class:`~pmutt.empirical.EmpiricalBase`

    Attributes
    ----------
        T_low : float
            Lower temperature bound (in K)
        T_high : float
            High temperature bound (in K)
        a : (9,) `numpy.ndarray`_
            NASA9 polynomial to use between T_low and T_high
    """
    def __init__(self, T_low, T_high, a):
        self.T_low = T_low
        self.T_high = T_high
        self.a = a

    def get_CpoR(self, T):
        """Calculate the dimensionless heat capacity

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
        Returns
        -------
            CpoR : float or (N,) `numpy.ndarray`_
                Dimensionless heat capacity

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """
        # Convert T to 1D numpy format
        if not _is_iterable(T):
            T = [T]
        T = np.array(T)

        CpoR = get_nasa9_CpoR(a=self.a, T=T)
        return CpoR

    def get_HoRT(self, T):
        """Calculate the dimensionless enthalpy

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
        Returns
        -------
            HoRT : float or (N,) `numpy.ndarray`_
                Dimensionless enthalpy

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """        
        # Convert T to 1D numpy format
        if not _is_iterable(T):
            T = [T]
        T = np.array(T)

        HoRT = get_nasa9_HoRT(a=self.a, T=T)
        return HoRT

    def get_SoR(self, T):
        """Calculate the dimensionless heat capacity

        Parameters
        ----------
            T : float or (N,) `numpy.ndarray`_
                Temperature(s) in K
        Returns
        -------
            CpoR : float or (N,) `numpy.ndarray`_
                Dimensionless heat capacity

        .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
        """        
        # Convert T to 1D numpy format
        if not _is_iterable(T):
            T = [T]
        T = np.array(T)

        SoR = get_nasa9_SoR(a=self.a, T=T)
        return SoR

    def to_dict(self):
        """Represents object as dictionary with JSON-accepted datatypes

        Returns
        -------
            obj_dict : dict
        """
        obj_dict = {
            'class': str(self.__class__),
            'type': 'singlenasa9',
            'T_low': self.T_low,
            'T_high': self.T_high,
            'a': list(self.a)
        }
        return obj_dict

    @classmethod
    def from_dict(cls, json_obj):
        """Recreate an object from the JSON representation.

        Parameters
        ----------
            json_obj : dict
                JSON representation
        Returns
        -------
            Nasa : Nasa object
        """
        json_obj = remove_class(json_obj)
        # Reconstruct statmech model
        json_obj['nasas'] = [json_to_pmutt(nasa) for nasa in json_obj['nasas']]
        json_obj['statmech_model'] = json_to_pmutt(json_obj['statmech_model'])
        json_obj['misc_models'] = json_to_pmutt(json_obj['misc_models'])
        return cls(**json_obj)

    def to_CTI(self, line_indent=False):
        if line_indent:
            line_adj = '                '
        else:
            line_adj = ''
        cti_str = ('{}NASA([{}, {}],\n'
                   '                     [{: 2.8E}, {: 2.8E}, {: 2.8E},\n'
                   '                      {: 2.8E}, {: 2.8E}, {: 2.8E},\n'
                   '                      {: 2.8E}, {: 2.8E}, {: 2.8E}])'.format(
                            line_adj, self.T_low, self.T_high, self.a[0],
                            self.a[1], self.a[2], self.a[3], self.a[4],
                            self.a[5], self.a[6], self.a[7], self.a[8]))
        return cti_str

def _fit_CpoR(T, CpoR, T_mid=None):
    """Fit a[0]-a[4] coefficients in a_low and a_high attributes given the
    dimensionless heat capacity data

    Parameters
    ----------
        T : (N,) `numpy.ndarray`_
            Temperatures in K
        CpoR : (N,) `numpy.ndarray`_
            Dimensionless heat capacity
        T_mid : float or iterable of float, optional
            Guess for T_mid. If float, only uses that value for T_mid. If
            list, finds the best fit for each element in the list. If None,
            a range of T_mid values are screened between the lowest value
            and highest value of T.
    Returns
    -------
        a_low : (7,) `numpy.ndarray`_
            Lower coefficients of NASA polynomial
        a_high : (7,) `numpy.ndarray`_
            Higher coefficients of NASA polynomial
        T_mid : float
            Temperature in K used to split the CpoR data


    .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
    """
    # If the Cp/R does not vary with temperature (occurs when no
    # vibrational frequencies are listed), return default values
    if (np.isclose(np.mean(CpoR), 0.) and np.isnan(variation(CpoR))) \
       or np.isclose(variation(CpoR), 0.) \
       or any([np.isnan(x) for x in CpoR]):
        T_mid = T[int(len(T)/2)]
        a_low = np.zeros(7)
        a_high = np.zeros(7)
        return a_low, a_high, T_mid

    # If T_mid not specified, generate range between 6th smallest data point
    # and 6th largest data point
    if T_mid is None:
        T_mid = T[5:-5]

    # If a single value for T_mid is chosen, convert to a tuple
    if not _is_iterable(T_mid):
        T_mid = (T_mid,)

    # Initialize parameters for T_mid optimization
    mse_list = []
    prev_mse = np.inf
    all_a_low = []
    all_a_high = []
    for T_m in T_mid:
        # Generate temperature data
        (mse, a_low, a_high) = _get_CpoR_MSE(T=T, CpoR=CpoR, T_mid=T_m)
        mse_list.append(mse)
        all_a_low.append(a_low)
        all_a_high.append(a_high)
        # Check if the optimum T_mid has been found by determining if the
        # fit MSE value for the current T_mid is higher than the previous
        # indicating that subsequent guesses will not improve the fit
        if mse > prev_mse:
            break
        prev_mse = mse

    # Select the optimum T_mid based on the highest fit R2 value
    min_mse = min(mse_list)
    min_i = np.where(min_mse == mse_list)[0][0]

    T_mid_out = T_mid[min_i]
    a_low_rev = all_a_low[min_i]
    a_high_rev = all_a_high[min_i]

    # Reverse array and append two zeros to end
    empty_arr = np.zeros(2)
    a_low_out = np.concatenate((a_low_rev[::-1], empty_arr))
    a_high_out = np.concatenate((a_high_rev[::-1], empty_arr))
    return a_low_out, a_high_out, T_mid_out


def _get_CpoR_MSE(T, CpoR, T_mid):
    """Calculates the mean squared error of polynomial fit.

    Parameters
    ----------
        T : (N,) `numpy.ndarray`_
            Temperatures (K) to fit the polynomial
        CpoR : (N,) `numpy.ndarray`_
            Dimensionless heat capacities that correspond to T array
        i_mid : int
            Index that splits T and CpoR arrays into a lower
            and higher range
    Returns
    -------
        mse : float
            Mean squared error resulting from NASA polynomial fit to T and CpoR
        p_low : (5,) `numpy.ndarray`_
            Polynomial corresponding to lower range of data
        p_high : (5,) `numpy.ndarray`_
            Polynomial corresponding to high range of data

    .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
    """
    low_condition = (T <= T_mid)
    high_condition = (T > T_mid)
    T_low = np.extract(condition=low_condition, arr=T)
    T_high = np.extract(condition=high_condition, arr=T)
    CpoR_low = np.extract(condition=low_condition, arr=CpoR)
    CpoR_high = np.extract(condition=high_condition, arr=CpoR)

    if len(T_low) < 5:
        warn('Small set of CpoR data between T_low and T_mid. '
             'Fit may not be desirable.', RuntimeWarning)
    if len(T_high) < 5:
        warn('Small set of CpoR data between T_mid and T_high. '
             'Fit may not be desirable.', RuntimeWarning)

    # Fit the polynomials
    p_low = np.polyfit(x=T_low, y=CpoR_low, deg=4)
    p_high = np.polyfit(x=T_high, y=CpoR_high, deg=4)

    # Calculate RMSE
    CpoR_low_fit = np.polyval(p_low, T_low)
    CpoR_high_fit = np.polyval(p_high, T_high)
    CpoR_fit = np.concatenate((CpoR_low_fit, CpoR_high_fit))
    mse = np.mean((CpoR_fit - CpoR)**2)
    return (mse, p_low, p_high)


def _fit_HoRT(T_ref, HoRT_ref, a_low, a_high, T_mid):
    """Fit a[5] coefficient in a_low and a_high attributes given the
    dimensionless enthalpy

    Parameters
    ----------
        T_ref : float
            Reference temperature in K
        HoRT_ref : float
            Reference dimensionless enthalpy
        T_mid : float
            Temperature to fit the offset
    Returns
    -------
        a6_low_out : float
            Lower a6 value for NASA polynomial
        a6_high_out : float
            Higher a6 value for NASA polynomial
    """
    a6_low_out = (HoRT_ref - get_nasa_HoRT(a=a_low, T=T_ref))*T_ref
    a6_high = (HoRT_ref - get_nasa_HoRT(a=a_high, T=T_ref))*T_ref

    # Correcting for offset
    H_low_last_T = get_nasa_HoRT(a=a_low, T=T_mid) + a6_low_out/T_mid
    H_high_first_T = get_nasa_HoRT(a=a_high, T=T_mid) + a6_high/T_mid
    H_offset = H_low_last_T - H_high_first_T
    a6_high_out = T_mid * (a6_high/T_mid + H_offset)

    return a6_low_out, a6_high_out


def _fit_SoR(T_ref, SoR_ref, a_low, a_high, T_mid):
    """Fit a[6] coefficient in a_low and a_high attributes given the
    dimensionless entropy

    Parameters
    ----------
        T_ref : float
            Reference temperature in K
        SoR_ref : float
            Reference dimensionless entropy
        T_mid : float
            Temperature to fit the offset
    Returns
    -------
        a7_low_out : float
            Lower a7 value for NASA polynomial
        a7_high_out : float
            Higher a7 value for NASA polynomial
    """
    a7_low_out = SoR_ref - get_nasa_SoR(a=a_low, T=T_ref)
    a7_high = SoR_ref - get_nasa_SoR(a=a_high, T=T_ref)

    # Correcting for offset
    S_low_last_T = get_nasa_SoR(a=a_low, T=T_mid) + a7_low_out
    S_high_first_T = get_nasa_SoR(a=a_high, T=T_mid) + a7_high
    S_offset = S_low_last_T - S_high_first_T
    a7_high_out = a7_high + S_offset

    return a7_low_out, a7_high_out    

def _calc_T_mid_mse_nasa9(T_mid, T_low, T_high, model, n_T=50):
    """Calculates the mean squared error associated with temperature intervals
    for NASA9 polynomials

    Parameters
    ----------
        T_mid : (N,) nd.ndarray
            Temperature intervals (in K) being evaluated
        T_low : float
            Lower temperature bound
        T_high : float
            Higher temperature bound
        model : Species object
            Object that can provide heat capacity at any temperature
        n_T : int
            Number of temperature values to evaluate between each interval
    Returns
    -------
        mse : float
            Total mean squared error
    """
    # T_mid should be between T_low and T_high
    if np.any(T_mid <= T_low) or np.any(T_mid >= T_high):
        return np.inf

    mse = 0.
    # Calculate MSE for each interval
    T_interval = np.concatenate([[T_low], T_mid, [T_high]])
    for T1, T2 in zip(T_interval, T_interval[1:]):
        T = np.linspace(T1, T2, n_T)
        # Generate heat capacity data
        CpoR = np.array([model.get_CpoR(T=T_i) for T_i in T])

        # Optimize NASA9 coefficients
        res = minimize(method='BFGS', args=(T, CpoR),
                       fun=_get_nasa9_mse, jac=_get_nasa9_mse_jacob,
                       x0=np.zeros(9))
        mse += res.fun
    return mse

def _get_nasa9_mse(a, T, CpoR):
    """Calculates the mean squared error associated with NASA9 coefficients

    Parameters
    ----------
        a : (9,) nd.ndarray
            Coefficients of NASA9 polynomial
        T : (N,) nd.ndarray
            Temperatures to evaluate the NASA9 coefficients in K
        CpoR : (N,) nd.ndarray
            Accurate dimensionless heat capacities corresponding to T
    Returns
    -------
        mse : float
            Total mean squared error
    """
    CpoR_fit = get_nasa9_CpoR(a, T)
    mse = np.mean((CpoR_fit - CpoR)**2)
    return mse

def _get_nasa9_mse_jacob(a, T, CpoR):
    """Calculates the Jacobian associated with NASA9 coefficients

    Parameters
    ----------
        a : (9,) nd.ndarray
            Coefficients of NASA9 polynomial
        T : (N,) nd.ndarray
            Temperatures to evaluate the NASA9 coefficients in K
        CpoR : (N,) nd.ndarray
            Accurate dimensionless heat capacities corresponding to T
    Returns
    -------
        jac : (9,) nd.ndarray
            Jacobian corresponding to a
    """
    CpoR_fit = get_nasa9_CpoR(a, T)
    error = CpoR_fit - CpoR
    jac = 2./float(len(T))*np.array([np.sum(error*(T**-2)),
                                     np.sum(error*(T**-1)),
                                     1.,
                                     np.sum(error*T),
                                     np.sum(error*(T**2)),
                                     np.sum(error*(T**3)),
                                     np.sum(error*(T**4)),
                                     0.,
                                     0.])
    return jac

def _fit_CpoR9(T, CpoR, T_low, T_high, T_mid):
    """Fit a[0]-a[6] coefficients in a_low and a_high attributes given the
    dimensionless heat capacity data

    Parameters
    ----------
        T : (N,) `numpy.ndarray`_
            Temperatures in K
        CpoR : (N,) `numpy.ndarray`_
            Dimensionless heat capacity
        T_mid : float or iterable of float, optional
            Guess for T_mid. If float, only uses that value for T_mid. If
            list, finds the best fit for each element in the list. If None,
            a range of T_mid values are screened between the lowest value
            and highest value of T.
    Returns
    -------
        a_low : (9,) `numpy.ndarray`_
            Lower coefficients of NASA polynomial
        a_high : (9,) `numpy.ndarray`_
            Higher coefficients of NASA polynomial
        T_mid : float
            Temperature in K used to split the CpoR data

    .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
    """
    # If the Cp/R does not vary with temperature (occurs when no
    # vibrational frequencies are listed), return default values
    if (np.isclose(np.mean(CpoR), 0.) and np.isnan(variation(CpoR))) \
       or np.isclose(variation(CpoR), 0.) \
       or any([np.isnan(x) for x in CpoR]):
       return [np.zeros(9)]*(len(T_mid)+1)

    a = []
    T_interval = np.concatenate([[T_low], T_mid, [T_high]])
    for T1, T2 in zip(T_interval, T_interval[1:]):
        # Find T and CpoR in interval
        condition = (T > T1) & (T <= T2)
        T_cond = np.extract(condition=condition, arr=T)
        CpoR_cond = np.extract(condition=condition, arr=CpoR)

        res = minimize(method='BFGS', args=(T_cond, CpoR_cond),
                       fun=_get_nasa9_mse, jac=_get_nasa9_mse_jacob,
                       x0=np.zeros(9))
        a.append(res.x)
    return a

def _fit_HoRT9(T_ref, HoRT_ref, a, T_mid):
    """Fit a[7] coefficient in a_low and a_high attributes given the
    dimensionless enthalpy

    Parameters
    ----------
        T_ref : float
            Reference temperature in K
        HoRT_ref : float
            Reference dimensionless enthalpy
        a : (N, 9) nd.ndarray
            NASA9 polynomial
        T_mid : float
            Temperature to fit the offset
    Returns
    -------
        a : (N, 9) nd.ndarray
            NASA9 polynomials with a[:, 7] position corrected for HoRT_ref
    """
    a[0][7] = (HoRT_ref - get_nasa9_HoRT(a=a[0], T=T_ref))*T_ref
    for i, row_a in enumerate(a[1:], start=1):
        a8_low = (HoRT_ref - get_nasa9_HoRT(a=a[i-1], T=T_ref))*T_ref
        a8_high = (HoRT_ref - get_nasa9_HoRT(a=a[i], T=T_ref))*T_ref

        HoRT_low = get_nasa9_HoRT(a=a[i-1], T=T_mid[i-1]) + a8_low/T_mid[i-1]
        HoRT_high = get_nasa9_HoRT(a=a[i], T=T_mid[i-1]) + a8_high/T_mid[i-1]
        HoRT_offset = HoRT_low - HoRT_high
        a[i][7] = T_mid[i-1]*(a8_high/T_mid[i-1] + HoRT_offset)

        HoRT_ref = HoRT_low
        T_ref = T_mid[i-1]
    return a

def _fit_SoR9(T_ref, SoR_ref, a, T_mid):
    """Fit a[8] coefficient in a_low and a_high attributes given the
    dimensionless entropy

    Parameters
    ----------
        T_ref : float
            Reference temperature in K
        SoR_ref : float
            Reference dimensionless entropy
        a : (N, 9) nd.ndarray
            NASA9 polynomial
        T_mid : float
            Temperature to fit the offset
    Returns
    -------
        a : (N, 9) nd.ndarray
            NASA9 polynomials with a[:, 8] position corrected for SoR_ref
    """
    a[0][8] = SoR_ref - get_nasa9_SoR(a=a[0], T=T_ref)
    for i, row_a in enumerate(a[1:], start=1):
        a9_low = SoR_ref - get_nasa9_SoR(a=a[i-1], T=T_ref)
        a9_high = SoR_ref - get_nasa9_SoR(a=a[i], T=T_ref)

        SoR_low = get_nasa9_SoR(a=a[i-1], T=T_mid[i-1]) + a9_low
        SoR_high = get_nasa9_SoR(a=a[i], T=T_mid[i-1]) + a9_high
        SoR_offset = SoR_low - SoR_high
        a[i][8] = a9_high + SoR_offset

        SoR_ref = SoR_low
        T_ref = T_mid[i-1]
    return a

def get_nasa_CpoR(a, T):
    """Calculates the dimensionless heat capacity using NASA polynomial form

    Parameters
    ----------
        a : (7,) `numpy.ndarray`_
            Coefficients of NASA polynomial
        T : float
            Temperature in K
    Returns
    -------
        CpoR: float
            Dimensionless heat capacity

    .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
    """
    T_arr = np.array([1., T, T**2, T**3, T**4, 0., 0.])
    return np.dot(a, T_arr)


def get_nasa_HoRT(a, T):
    """Calculates the dimensionless enthalpy using NASA polynomial form

    Parameters
    ----------
        a : (7,) `numpy.ndarray`_
            Coefficients of NASA polynomial
        T : float
            Temperature in K
    Returns
    -------
        HoRT : float
            Dimensionless enthalpy

    .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
    """
    T_arr = np.array([1., T/2., (T**2)/3., (T**3)/4., (T**4)/5., 1./T, 0.])
    return np.dot(a, T_arr)


def get_nasa_SoR(a, T):
    """Calculates the dimensionless entropy using NASA polynomial form

    Parameters
    ----------
        a : (7,) `numpy.ndarray`_
            Coefficients of NASA polynomial
        T : float
            Temperature in K
    Returns
    -------
        SoR : float
            Dimensionless entropy

    .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
    """
    T_arr = np.array([np.log(T), T, (T**2)/2., (T**3)/3., (T**4)/4., 0., 1.])
    return np.dot(a, T_arr)


def get_nasa9_CpoR(a, T):
    """Calculates the dimensionless heat capacity using NASA polynomial form

    Parameters
    ----------
        a : (9,) `numpy.ndarray`_
            Coefficients of NASA polynomial
        T : float
            Temperature in K
    Returns
    -------
        CpoR: float
            Dimensionless heat capacity

    .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
    """
    T_arr = np.array([T**-2, T**-1, 1., T, T**2, T**3, T**4, 0., 0.])
    return np.dot(a, T_arr)


def get_nasa9_HoRT(a, T):
    """Calculates the dimensionless enthalpy using NASA polynomial form

    Parameters
    ----------
        a : (9,) `numpy.ndarray`_
            Coefficients of NASA polynomial
        T : float
            Temperature in K
    Returns
    -------
        HoRT : float
            Dimensionless enthalpy

    .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
    """
    T_arr = np.array([-(T**-2), np.log(T)/T, 1., T/2., (T**2)/3., (T**3)/4.,
                      (T**4)/5., 1./T, 0.])
    return np.dot(a, T_arr)


def get_nasa9_SoR(a, T):
    """Calculates the dimensionless entropy using NASA polynomial form

    Parameters
    ----------
        a : (9,) `numpy.ndarray`_
            Coefficients of NASA polynomial
        T : float
            Temperature in K
    Returns
    -------
        SoR : float
            Dimensionless entropy

    .. _`numpy.ndarray`: https://docs.scipy.org/doc/numpy/reference/generated/numpy.ndarray.html
    """
    T_arr = np.array([-(T**-2)/2., -(T**-1), np.log(T), T, (T**2)/2., (T**3)/3.,
                      (T**4)/4., 0., 1.])
    return np.dot(a, T_arr)