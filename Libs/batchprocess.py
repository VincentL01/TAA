from pathlib import Path
import re
from Libs.executor import *
from Libs.misc import sort_paths_by_parent, hyploader, nanlize

from . import tests

import logging
logger = logging.getLogger(__name__)


keywords = [x.split(' ')[0].lower() for x in tests]
test_execs = [noveltank_exec, shoaling_exec, mirrorbiting_exec, socialinteraction_exec, predatoravoidance_exec]

class MY_CONDITION():

    def __init__(self, test_name, condition, condition_path, no_gap, hyp_name, hyp_batch_dir):
        
        self.test_name = test_name

        self.condition = condition # A, B, C

        self.no_gap = no_gap


        self.hyp_path = hyp_batch_dir / condition / hyp_name
        if self.hyp_path.exists():
            self.hyp = self.HypLoader()
        else:
            self.hyp = {}

        self.trajectory_format = self.set_trajectory_type()

        self.targets = self.find_targets(condition_path)
     

    def HypLoader(self):

        data = hyploader(self.hyp_path)
        logger.info(f'Loading hyp from {self.hyp_path}')
        logger.debug(f'Loaded hyp: {data}')
        
        return data

    def find_targets(self, condition_path):

        # find all directories under condition_path
        all_dirs = [x for x in condition_path.iterdir() if x.is_dir()]
        logger.debug(f'Found {len(all_dirs)} directories under {condition_path}')

        trajectories = condition_path.glob(f'**/{self.trajectory_format}')
        valid_dirs = [x.parent for x in trajectories]
        if len(valid_dirs) == 0:
            logger.warning(f'No trajectories found in {condition_path}')
            return {}

        pseudo_trajectories = []
        for d in all_dirs:
            if d in valid_dirs:
                pseudo_trajectories.append(d / self.trajectory_format)
            else:
                pseudo_trajectories.append(d / 'pseudo.txt')

        pseudo_trajectories = sort_paths_by_parent(pseudo_trajectories)
        logger.info(f'Found {len(valid_dirs)} existed trajectories in {condition_path}')
        logger.debug(f'Existed trajectories: {len(valid_dirs)}, pseudo trajectories: {len(all_dirs)-len(valid_dirs)}')

        targets = {trajectory.parent.name: trajectory for trajectory in pseudo_trajectories}
        # if any key of targets is not int, logger.warning
        if any([not x.isdigit() for x in targets.keys()]):
            logger.error(f'Found non-integer fish group in {condition_path}')
        targets = self.priotize_data(targets, mode = 'last')
        
        return targets       


    def priotize_data(self, input_dict, mode = 'last'):

        # mode can be the sub-num to keep or 'first' or 'last'
        # sub-num is like the 9 in a folder named "1-9"
        
        logger.info(f"Prioritizing data... mode = {mode}")

        key_group = {}
        for key in input_dict.keys():
            k = key.split('-')[0].strip()
            if k not in key_group:
                key_group[k] = [key]
            else:
                key_group[k].append(key)

        def sub_num(input_str):
            return int(input_str.split('-')[1].strip())

        #if mode is not first or last, try to convert to int
        if mode not in ['first', 'last']:
            logger.debug("Mode is not first or last, trying to convert to int...")
            try:
                chosen = int(mode)
                logger.debug(f"Chosen {chosen} as the sub-num to keep")
            except:
                logger.debug("Failed to convert to int, using mode=last as default")
                mode = 'last'

        for k, v in key_group.items():
            remove_list = []
            if len(v) > 1:
                addition_list = [x for x in v if x != k]
                if mode == 'first':
                    remove_list = addition_list
                elif mode == 'last':
                    last_num = max([sub_num(x) for x in addition_list])
                    remove_list = [x for x in addition_list if sub_num(x) != last_num]
                    remove_list.append(k)
                else:
                    if chosen in [sub_num(x) for x in addition_list]:
                        remove_list = [x for x in addition_list if sub_num(x) != chosen]
                        remove_list.append(k)         
                    
            # print(remove_list)
            logger.debug(f'Removing {remove_list} from {k}')
            for key in remove_list:
                input_dict.pop(key)
        
        return input_dict



    def set_trajectory_type(self):

        if self.no_gap:
            trajectory_format = "trajectories_nogaps.txt"
        else:
            trajectory_format = "trajectories.txt"

        logger.info(f'Using {trajectory_format} as trajectory format')

        return trajectory_format
    

    def analyze(self, target_name, seg_num = 1):

        if self.test_name not in tests:
            raise ValueError(f'{self.test_name} is not a valid test name')
        
        test_index = tests.index(self.test_name)
        logger.info(f'Running test: {self.test_name}...')
        test_exec = test_execs[test_index]

        for target, target_path in self.targets.items():
            logger.debug(f'Scanning {target} if == {target_name}')
            if target == target_name:
                logger.debug(' Matched !')

                if target_path.name == 'pseudo.txt':
                    pseudo = True
                    logger.debug(f"Target {target} is pseudo result")
                    # change target_path to any non-pseudo path in self.targets.values()
                    target_path = [x for x in self.targets.values() if x.name != 'pseudo.txt'][0]
                else:
                    pseudo = False
                    logger.debug(f"Target {target} is real result")

                if test_index == 0:
                    results = test_exec(target_path, project_hyp = self.hyp, seg_num = seg_num)
                    # test_exec("1", "../PROJECT/{num} - Test/{char} - Treatment ({ordinal} Batch)/{target}/.txt")
                else:
                    results = test_exec(target_path, project_hyp = self.hyp)

                if pseudo:
                    # NaN-lize the results
                    results = nanlize(results, test_index)
                    logger.debug(f"NaN-lized results of {target}")

                return results # in format [key, value], not {key: value} for easy retrieval


    def info(self):

        output_text = f'In condition {self.condition}, we have: \n'
        for target, target_path in self.targets.items():
            output_text += f'Fish group {target} : {target_path} \n'

        print(output_text)





class MY_BATCH():

    def __init__(self, test_name, batch_num, batch_paths, no_gap, hyp_name, static_dir):

        self.test_name = test_name

        self.num = batch_num

        self.conditions = self.extract_conditions(batch_paths)

        hyp_batch_dir = static_dir / f"Batch {self.num}"
        
        self.condition = {}
        for condition, cond_path in self.conditions.items():
            self.condition[condition] = MY_CONDITION(test_name = self.test_name, 
                                                     condition = condition, 
                                                     condition_path = cond_path, 
                                                     no_gap = no_gap, 
                                                     hyp_name = hyp_name,
                                                     hyp_batch_dir = hyp_batch_dir)
            

    def extract_conditions(self, batch_paths):

        def get_name(pathlib_path):

            name = pathlib_path.name.split('-')[0]
            name = name.strip()

            return name

        conditions = {}
        for batch_path in batch_paths:
            logger.info(f'Extracting condition name from {batch_path}')
            logger.debug(f'Condition name is {get_name(batch_path)}')
            conditions[get_name(batch_path)] = batch_path

        return conditions


    def info(self):

        output_text = f"In Batch {self.num}, we have: \n"
        for condition, cond_path in self.conditions.items():
            output_text += f"Condition {condition} : {cond_path} \n"
        
        print(output_text)




class MY_DIR():

    def __init__(self, name, dir_path, no_gap = False):

        hyp_name = f"hyp_{name.split(' ')[0].lower()}.json"

        project_dir = Path(dir_path).parent
        static_dir = project_dir / 'static'

        self.test_name = name
        self.test_dir = dir_path
        self.batches = self.find_batches() # batches[1] = 1st Batch results paths
        self.batches_num = len(self.batches)
        self.batch = {}
        for i in range(self.batches_num):
            self.batch[i+1] = MY_BATCH(test_name=self.test_name, 
                                       batch_num = i+1, 
                                       batch_paths = self.batches[i+1], 
                                       no_gap = no_gap, 
                                       hyp_name = hyp_name,
                                       static_dir = static_dir)

    # def HypLoader(self, hyp_path):

    #     data = hyploader(hyp_path)
        
    #     return data


    def find_batches(self):

        # Create a regular expression to match ordinals (1st, 2nd, 3rd, etc.)
        ordinal_regex = re.compile(r"\b(\d+)(st|nd|rd|th)\b")

        # Initialize a dictionary to hold the groups of directories
        batches = {}

        subdirectories = [x for x in self.test_dir.glob("*/") if x.is_dir()]
        for subdirectory in subdirectories:
            # Check if the subdirectory name contains an ordinal
            match = ordinal_regex.search(subdirectory.name)
            if match:
                # Get the ordinal number and convert it to an integer
                ordinal_number = int(match.group(1))
                # Add the subdirectory to the appropriate group
                if ordinal_number not in batches:
                    batches[ordinal_number] = []
                batches[ordinal_number].append(subdirectory)

        # # Print the results
        # for key in sorted(batches.keys()):
        #     print("batches[{}] = {}".format(key, batches[key]))
        
        return batches
    
    
    def info(self):

        output_text = f"In {self.test_name} Test, we have: \n"
        for num, batch in self.batches.items():
            output_text += f"Batch {num} : {batch} \n"
        
        print(output_text)
