try:
    from ursina.prefabs.bloom_effect import BloomEffect
    print("Found in ursina.prefabs.bloom_effect")
except:
    try:
        from ursina.bloom import Bloom
        print("Found in ursina.bloom")
    except:
        print("Not found")
