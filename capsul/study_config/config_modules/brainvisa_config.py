import os
from traits.api import Directory, Undefined
from soma import config as soma_config
from capsul.study_config.study_config import StudyConfigModule


class BrainVISAConfig(StudyConfigModule):
    def __init__(self, study_config, configuration):
        super(BrainVISAConfig, self).__init__(study_config, configuration)
        study_config.add_trait('shared_directory',Directory(
            Undefined,
            output=False,
            desc='Study shared directory'))

        study_config.shared_directory = soma_config.BRAINVISA_SHARE
