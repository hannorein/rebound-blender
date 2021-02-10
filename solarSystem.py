from bpy import context, data, ops
import os, shutil, struct
import rebound
import numpy as np

uniqueSimulationID = "SolarSystem"
workingDirectory = "/tmp/"+uniqueSimulationID # Warning: This directory will be deleted

def resetBlender(removeMaterials=False):
    # Remove all Objects
    for key in context.scene.objects.keys():
        if "REBOUND" in key:
            data.objects.remove(context.scene.objects[key],do_unlink=True)    
    # Remove all Materials
    if removeMaterials:
        for key in data.materials.keys():
            if "REBOUND" in key:
                data.materials.remove(data.materials[key],do_unlink=True)    
    # Remove all collections
    for key in data.collections.keys():
        if "REBOUND" in key:
            data.collections.remove(data.collections[key])
    # Remove working Directory
    if os.path.exists(workingDirectory) and os.path.isdir(workingDirectory):
        shutil.rmtree(workingDirectory)
    os.mkdir(workingDirectory)    
            
def getSimulationEmpty(sim):
    # All Simulation Data is added under this "Empty".
    # This allows for multiple simulations to be added.
    name = "REBOUND Simulation (%s)" % uniqueSimulationID
    if name in data.collections:
        empty = data.collections[name]
    else:
        empty = data.collections.new(name)
        context.scene.collection.children.link(empty)
    return empty

def addOrbits(sim, pRange=None, Npts=32,scale=0.1):
    # Add orbits to Blender
    empty = getSimulationEmpty(sim)
    emptyo = data.collections.new("REBOUND Orbits (%s)"%uniqueSimulationID)
    empty.children.link(emptyo)  
    if not pRange:
        pRange = range(1,sim.N) 
    for i in pRange:  
        curveData = data.curves.new("mycurve", type="CURVE")
        curveData.dimensions = "3D"
        curveData.resolution_u = 4
        curve = curveData.splines.new("NURBS")
        curve.points.add(Npts-1)
        
        curve.use_cyclic_u = True
        xyz = sim.particles[i].sample_orbit(Npts=Npts,duplicateEndpoint=False)
        for j in range(Npts):
             curve.points[j].co = (*xyz[(j-1)%Npts],1 )
        orbit = data.objects.new("curveob", curveData)
        scn = context.collection
        orbit.name="REBOUND Orbit %d (%s)"%(i,uniqueSimulationID)     
        orbit.data.bevel_depth = scale
        emptyo.objects.link(orbit)#.parent = emptyo

def addParticles(sim, pRange=None, scale=None, subdivisions=2):
    # Adds particles to Blender
    empty = getSimulationEmpty(sim)
    emptyp = data.collections.new("REBOUND Particles (%s)"%uniqueSimulationID)
    empty.children.link(emptyp)
    
    
    if not pRange:
        pRange = range(0,sim.N) 
    for i in pRange:
        p = sim.particles[i]
        if scale:
            s = scale
        else:
            if p.r>0:
                s = 2.*p.r
            else:
                s = 0.1
        # Create an empty mesh and the object.
        name = "REBOUND Particle %d (%s)"%(i,uniqueSimulationID)        
        ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions,scale=(s,s,s),location=(p.x,p.y,p.z))
        sphere = context.active_object
        context.scene.collection.objects.unlink(sphere)
        sphere.name = name

        emptyp.objects.link(sphere)#.parent = emptyp
    
def insertOrbitsKeyframe(sim, pRange=None):
    # Creates or appends a pc2 file to store time dependent
    # mesh data for Orbits
    empty = getSimulationEmpty(sim)
    if not pRange:
        pRange = range(1,sim.N) 
    for i in pRange:  
        orbit_curve = context.scene.objects["REBOUND Orbit 1 (%s)"%uniqueSimulationID]
        numPoints = len(orbit_curve.data.splines[0].points)

        # .pc2 files have a header defined as such:
        # char    cacheSignature[12];   // Will be 'POINTCACHE2' followed by a trailing null character.
        # int     fileVersion;          // Currently 1
        # int     numPoints;            // Number of points per sample
        # float   startFrame;           // Corresponds to the UI value of the same name.
        # float   sampleRate;           // Corresponds to the UI value of the same name.
        # int     numSamples;           // Defines how many samples are stored in the fi

        fp = workingDirectory + "/ReboundOrbitAnimation%d.pc2"%i
        if not os.path.exists(fp):
            with open(fp, "wb") as file:
                for b in "POINTCACHE2\0":
                    headerStr = struct.pack("c", bytes(b,"ascii"))
                    file.write(headerStr)
                headerFormat='<iiffi'
                headerStr = struct.pack(headerFormat, 1, numPoints, 0., 1, 0)
                file.write(headerStr)
        with open(fp, "rb+") as file:         
            file.seek(12+4*4,0)
            nf_i = file.read(4) 
            nf = struct.unpack("<i",nf_i)[0]
            file.seek(12+4*4,0)
            file.write(struct.pack("<i",nf+1))
   
            file.seek(0,2)
            # Rool to align uv coordinates
            pd = np.roll(np.array(sim.particles[i].sample_orbit(Npts=numPoints,duplicateEndpoint=False),dtype="float32"),1,axis=0).flatten()
            pd.tofile(file)

        orbit_curve = context.scene.objects["REBOUND Orbit %d (%s)"%(i,uniqueSimulationID)]    
        hasmod = False
        for mod in orbit_curve.modifiers:
            if mod.type =="MESH_CACHE":
                hasmod = True
        if not hasmod:
            orbit_curve.modifiers.new("MeshCache",'MESH_CACHE')
            orbit_curve.modifiers["MeshCache"].use_apply_on_spline = True
            orbit_curve.modifiers["MeshCache"].cache_format = 'PC2'
            orbit_curve.modifiers["MeshCache"].filepath = fp


def insertParticlesKeyframe(sim, pRange=None):       
    if not pRange:
        pRange = range(0,sim.N) 
    for i in pRange:  
        p = context.scene.objects["REBOUND Particle %d (%s)"%(i,uniqueSimulationID)]    
        p.location = sim.particles[i].xyz
        p.keyframe_insert(data_path="location")

# Remove all previous REBOUND data from Blender
resetBlender()

# We're using the Solar System as a test case
sim = rebound.Simulation()
rebound.data.add_solar_system(sim)

# Add the particles and orbits at keyframe 0
context.scene.frame_set(0)
addParticles(sim,scale=0.09,subdivisions=4)
addOrbits(sim,scale=0.01)

# We're adding 100 keyframes
for i in range(100):
    context.scene.frame_set(i)
    
    # For each keyfrane, we're updating the orbit and particle data
    insertOrbitsKeyframe(sim)
    insertParticlesKeyframe(sim)

    sim.integrate(sim.t+0.03)

# Reset keyframe to 0
context.scene.frame_set(0)

