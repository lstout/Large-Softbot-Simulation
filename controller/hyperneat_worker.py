from __future__ import division
import ConfigParser
import shutil
from subprocess import CalledProcessError
import threading, time, subprocess, os
from db import DB
import random
import xml.etree.cElementTree as ET
import disease_functions

class HNWorker(threading.Thread):
    """ Thread for HyperNEAT worker... runs until cancelled or till max waiting time
    """

    config = ConfigParser.RawConfigParser()
    pause_time = 2
    queue_len = 12
    max_waiting_time = 60 * 60  # 60seconds * 60min = 1 hour in seconds
    base_path = ""
    pop_path = "population/"
    hn_path = "~/EC14-HyperNEAT/out/"
    hn_save_path = "hn_output/"
    hn_binary = "./Hypercube_NEAT"
    hn_params_file = "softbotTest.dat"
    suffix_genome = "_genome.xml"
    suffix_vox = "_vox.vxa"
    hn_trash_file = "Softbots--{0}---gen-Genchamp-AvgFit.txt"
    hn_stray_files =["md5sumTMP.txt"]
    # hn_binary = "python HyperNEATdummy.py"
    debug = False
    db = None
    mutate = False

    def readConfig(self, config_path):

        self.config.read(config_path)

        self.exp_name = self.config.get('Experiment', 'name')
        self.path_prefix = self.config.get('Experiment', 'path_prefix')
        self.debug = self.config.get('Experiment', 'debug')

        self.base_path = os.path.expanduser(self.path_prefix + self.exp_name) + "/"

        self.hn_path = self.config.get('Hyperneat', 'hn_path')
        self.hn_save_path = self.config.get('Hyperneat', 'hn_save_path')
        self.hn_binary = self.config.get('Hyperneat', 'hn_binary')
        self.hn_params_file = self.config.get('Hyperneat', 'hn_params_file')
        self.suffix_genome = self.config.get('Hyperneat', 'suffix_genome')
        self.suffix_vox = self.config.get('Hyperneat', 'suffix_vox')

        self.pause_time = self.config.getint('Workers', 'pause_time')
        self.queue_length = self.config.getint('Workers', 'queue_len')
        self.max_waiting_time = self.config.getint('Workers', 'max_waiting_time')

        self.pl_path = self.config.get('Lifetimes', 'pl_path')
        self.cost_muscle = self.config.getfloat('Lifetimes', 'cost_muscle')
        self.cost_soft = self.config.getfloat('Lifetimes', 'cost_soft')
        self.energy_unit = self.config.getfloat('Lifetimes', 'energy_unit')
        self.starting_energy = self.config.getfloat('Lifetimes', 'starting_energy')

        self.disease = self.config.getboolean('Disease', 'disease')
        indiv_prob_fn = self.config.get('Disease', 'indiv_function')
        self.indiv_prob_fn = getattr(disease_functions, indiv_prob_fn)
        cell_prob_fn = self.config.get('Disease', 'cell_function')
        self.cell_prob_fn = getattr(disease_functions, cell_prob_fn)




    def __init__(self, dbParams, config_path):
        threading.Thread.__init__(self)
        self.db = DB(dbParams[0], dbParams[1], dbParams[2], dbParams[3])
        self.readConfig(config_path)

        # individuals will be found here: self.base_path + self.pop_path + str(indiv)
        self.hn_path = os.path.expanduser(self.hn_path)
        self.pop_path = os.path.expanduser(self.base_path + self.pop_path)
        self.pl_path = os.path.expanduser(self.base_path + self.pl_path)
        self.hn_save_path = os.path.expanduser(self.base_path + self.hn_save_path)

        self.stopRequest = threading.Event()

    def run(self):
        """ main thread function
        :return: None
        """
        waitCounter = 0
        startTime = time.time()
        todos = set()
        while not self.stopRequest.isSet() and waitCounter < self.max_waiting_time:
            newTodos = self.checkForTodos()
            todos |= set(newTodos)

            if len(todos) > 0:
                todoTmp = []
                for _ in range(min(self.queue_length, len(todos))):
                    todoTmp.append(todos.pop())
                self.execHN(todoTmp)
                self.preprocessBeforeVox(todoTmp)
                waitCounter = 0
            else:
                waitCounter += time.time() - startTime
                startTime = time.time()

                if self.debug:
                    print("HN: sleeping now for " + str(self.pause_time) + "s")
                self.stopRequest.wait(self.pause_time)

        print ("Thread: got exit signal... here I can do some last cleanup stuff before quitting")

    def kill(self, timeout=None):
        """ function to terminate the thread (softly)
        :param timeout: not implemented yet
        :return: None
        """
        if self.debug:
            print("HN: got kill request for thread")
        self.stopRequest.set()
        super(HNWorker, self).join(timeout)

    def checkForTodos(self):
        """ check the DB or the filesystem and look if there are any new individuals that need to be hyperneated
        :return: simple python list with the names of the individuals that are new and need to be hyperneated
        """
        todos = self.db.getHNtodos()
        print "HN: Found", len(todos), "todo(s)"
        return todos

    def execHN(self, todos):
        """ execute HyperNEAT for all the individuals in the input list
        :param todos: list with strings containing the names of the individuals to be hyperneated
        :return: None
        """
        for indiv in todos:
            parents = self.db.getParents(indiv)
            hn_params = " ".join(map(str,parents))  # parent will be a list of size 0|1|2
            print("HN: creating individual (calling HN binary): " + str(indiv) )
            self.runHN(indiv, hn_params)
            print("HN: finished creating individual: " + str(indiv))

            if (len(parents) == 2): # mutate if the indiv has 2 parents
                print("HN: mutating individual: " + str(indiv) )
                self.runHN(indiv, str(indiv))
                print("HN: finished mutating individual: " + str(indiv))


    def preprocessBeforeVox(self, todos):
        """ run all the freshly-generated individuals through preprocessing to place them in an arena etc.
        :param todos: list with strings containing the names of the individuals from the last HN run
        :return: None
        """
        if self.debug:
            print("HN: preprocessing")
        for indiv in todos:
            indiv_hn = self.hn_save_path + str(indiv) + self.suffix_vox
            indiv_pop = self.pop_path + str(indiv) + self.suffix_vox
            indiv_pl = self.pl_path + str(indiv) + self.suffix_vox
            while not os.path.isfile(indiv_hn):
                print indiv, 'not born alive, recreating!'
                self.execHN([indiv])
            if self.debug:
                print("HN: preprocessing individual " + str(indiv))
            shutil.copy2(indiv_hn, indiv_pl)
            shutil.move(indiv_hn, indiv_pop)

            self.calculateLifetime(indiv)

            if self.disease:
                disease_functions.apply_disease(indiv_pop, self.indiv_prob_fn, self.cell_prob_fn)

            if (os.path.isfile(self.hn_path + self.hn_trash_file.format(indiv))):
                os.remove(self.hn_path + self.hn_trash_file.format(indiv))

            self.db.markAsHyperneated(indiv)

        for f in self.hn_stray_files:
            if (os.path.isfile(self.hn_path + f)):
                try:
                    os.remove(self.hn_path + f)
                except:
                    continue
        self.db.flush()

    def calculateLifetime(self,indiv):
        """Calculates and edits an individual's lifetime based on its genome
        """
        tree = ET.ElementTree(file=self.pop_path + str(indiv) + self.suffix_vox)
        root = tree.getroot()
        layers = root.find('VXC').find('Structure').find('Data').findall('Layer')

        dna = ""
        for layer in layers:
            dna += str(layer.text).strip()

        dna_length = len(dna)

        count_empty = dna.count('0')
        count_soft = dna.count('1')
        count_hard = dna.count('2')
        count_active = dna.count('3') + dna.count('4')
        count_length = count_empty + count_soft + count_hard + count_active

        lifetime = self.energy_unit * (self.starting_energy - ((count_soft * self.cost_soft) + (count_active * self.cost_muscle)))

        root.find('Simulator').find('StopCondition').find('StopConditionValue').text = str(lifetime)
        try:
            tree.write(self.pop_path + str(indiv) + self.suffix_vox)
        except:
            print 'HN (ERROR): Could not write to', self.pop_path + str(indiv) + self.suffix_vox
        
    def runHN(self, indiv, hn_params):
        """ run hyperneat with its parameters
        :param hn_params: string with either 0, 1 or 2 parents, just the IDs (no file suffix), separated by a space
        :return: None
        """
        if hn_params:
        	hn_params = [self.hn_save_path + f for f in hn_params.split(" ")]
		hn_params = " ".join(hn_params)
	hn_string = "-I " + self.hn_params_file + " -R $RANDOM -O " +self.hn_save_path + str(indiv) + " -ORG " + hn_params
        print self.hn_binary, hn_string
        try:
            subprocess.check_call(self.hn_binary + " " + hn_string,
                                  cwd=self.hn_path,
                                  stdout=open(self.base_path + "logs/" + "hn.stdout.log", "w"),
                                  stderr=open(self.base_path + "logs/" + "hn.stderr.log", "w"),
                                  stdin=open(os.devnull),
                                  shell=True)
        except CalledProcessError as e:
            print ("HN: during HN execution there was an error:")
            print (str(e.returncode))
            quit()
