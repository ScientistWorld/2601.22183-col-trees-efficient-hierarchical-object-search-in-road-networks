# Experiment Overview

All experiments run on the North-West US road network: 1.09M vertices, travel-time edges, from the 9th DIMACS
Challenge. Object sets are real OpenStreetMap POI categories mapped to vertices, or uniform random vertex samples
at densities 0.001, 0.01 and 0.1 (about 1,000 to 109,000 objects). The real categories hold 50 to 5,000 objects.
The dense sets test whether the savings hold as objects crowd together, which is where methods that check
objects one by one degrade fastest.
The evaluator owns every network distance. A method only sees what it asks for, and the evaluator counts what it asks for.

## kfn

Tests whether exact k farthest-neighbor queries (k=10) can be answered without retrieving and checking most of the
object set. Brute force has to evaluate every object, because the farthest objects cannot be found by expanding
outward from the query.

## aknn

Tests exact aggregate k nearest-neighbor queries for a group of 8 query vertices, with max and sum aggregates.
The goal is to examine only a small fraction of the objects and compute few exact distances.

## range

Tests exact range queries: report every object within 2.5% of the network diameter. The goal is to settle
whole groups of objects as inside or outside the range without examining each one.

In every experiment the work counted is what a method takes out of its index: the objects it examines
individually, and the index nodes holding objects that it opens. The exact distances it asks for are
counted as well.

Every experiment also measures the cost side of the claim. Answers must be exact, and the index must stay
within a fixed size and construction-work budget. Any method can trade more index for less query work,
so the budget is what makes the scores comparable.
