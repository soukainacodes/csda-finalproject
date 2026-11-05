"""The attacker AI: a (1+lambda) evolutionary search over the disguise genome.

HONEST STATUS (part of the DEMOTED arms-race framework): fitness = the Watcher's detection rate
on the twin (lower is better for the attacker). In the synthetic backend this does read the
defender's feedback and hill-climb; but in the live/serial backends there is no offline fitness,
so the loop just calls mutate() (random tweaks). And on real hardware it never actually evades
(the curve is flat). So this is an evasion FRAMEWORK, not a demonstrated AI-vs-AI result. See
experiments/ml-watcher-limitations.md.
"""
import random
from .synth import default_genome, genome_space


class Attacker:
    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.genome = default_genome()
        self.space = genome_space()

    def propose(self) -> dict:
        return dict(self.genome)

    def mutate(self, g: dict) -> dict:
        child = dict(g)
        for _ in range(self.rng.randint(1, 2)):
            key = self.rng.choice(list(self.space.keys()))
            child[key] = self.rng.choice(self.space[key])
        return child

    def adapt(self, fitness, offspring: int = 6) -> float:
        """Evolve one generation against a fitness callback (lower = more
        evasive). Returns the best (lowest) fitness found."""
        best, best_f = self.genome, fitness(self.genome)
        for _ in range(offspring):
            cand = self.mutate(self.genome)
            f = fitness(cand)
            if f < best_f:
                best, best_f = cand, f
        self.genome = best
        return best_f
