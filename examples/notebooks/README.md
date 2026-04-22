# NOTHING TO SEE HERE
***April 2, 2026***

I'm putting this up on GitHub finally, but in doing so have been finding a lot of cruft that I had meant to clean up but never got around to. There's actually only *ONE* tutorial notebook here, [graphulator_tutorial.ipynb](graphulator_tutorial.ipynb) and even that got hijacked to start working on automating the symbolic representation (via SymPy) of our graph calculations incl. Kron reduction (Schur complement calculation). That being said there are a lot of other notebooks that I had been using for testing and development. If you're super curious, you can take a look and get an idea of all the tedious details that went into figuring out to automate the graph scattering calculations from a dictionary-based graph representation.

In the end, if you want to use any of the graph code to automate more complicated calculations than you might set up by hand in the Paragraphulator GUI, you can just export the both SymPy and numerical graph scattering python code directly and paste into your own notebook. It's largely self-explanatory when you see it, but if you have trouble, you can try to post an issue on GitHub and I'll try to help out. I also plan to add more tutorial notebooks in the future, so if you have any suggestions for what you'd like to see, please let me know!

-JA