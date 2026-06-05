"""Various utility functions"""

def get_oldest_mcp_parent(mcp, n_iters=0):
    """Recursively look for the oldest parent of the input MCParticle"""
    n_parents = len(mcp.getParents())
    if (n_parents < 1):
        return mcp, n_iters
    for iP in range(n_parents):
        parent = mcp.getParents()[iP]
        # Skipping if the particle is its own parent
        if parent is mcp:
            continue
        return get_oldest_mcp_parent(parent, n_iters+1)
