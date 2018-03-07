import unittest
import six
import sys

try:
    import nipype.interfaces.spm as spm
except ImportError:
    raise Warning('test not performed because Nipype is not installed')

from traits.api import Float, CTrait, File, Directory
from traits.api import Undefined

from soma.controller.trait_utils import (
    get_trait_desc, is_trait_value_defined, is_trait_pathname,
    trait_ids)

import capsul


class TestUtils(unittest.TestCase):
    """ Class to test the utils function.
    """

    def test_trait_string_description(self):
        """ Method to test if we can build a string description for a trait.
        """
        trait = CTrait(0)
        trait.handler = Float()
        trait.ouptut = False
        trait.optional = True
        trait.desc = "bla"
        manhelp = get_trait_desc("float_trait", trait, 5)
        self.assertEqual(
            manhelp[0],
            "float_trait: a float (['Float'] - optional, default value: 5)")
        self.assertEqual(manhelp[1], "    bla")

    def test_trait(self):
        """ Method to test trait characterisitics: value, type.
        """
        self.assertTrue(is_trait_value_defined(5))
        self.assertFalse(is_trait_value_defined(""))
        self.assertFalse(is_trait_value_defined(None))
        self.assertFalse(is_trait_value_defined(Undefined))

        trait = CTrait(0)
        trait.handler = Float()
        self.assertFalse(is_trait_pathname(trait))
        for handler in [File(), Directory()]:
            trait.handler = handler
            self.assertTrue(is_trait_pathname(trait))



def test():
    """ Function to execute unitest
    """
    suite = unittest.TestLoader().loadTestsFromTestCase(TestUtils)
    runtime = unittest.TextTestRunner(verbosity=2).run(suite)
    return runtime.wasSuccessful()


if __name__ == "__main__":
    test()
