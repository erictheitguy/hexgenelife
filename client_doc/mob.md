# Mob

See `MobBehavior.md` and `MobBrain.md`

The mobs should be evoling through breeding. 
When breeding the mob should look for a partner that it considers to the best match for it that would result in children that would produce the fitest offspring. 

The long term of the project is to implement systems that allow for a wide diveregent from the starting point. While the starting point is expected to start with just two types of mobs (prey and predator) it is hoped that they start differing into type styles. Wether this is through behavior tendencies or through body styles. 

The game world should have systems in place that have interactions for different mob phyiscal characteristics. This will help force a divergement of the mobs based upon the phyiscal body and the behaviors of the mobs. 

When talking about a mob's genes it will consist of the phyiscal attributes that a mob can have along with the malleability of the brain. When a mob is born it is given the intial thinking tree/flow of the parents based upon the genetic algrothims modfications if any are present. 

We will use Taxonomic rank species, genus, tribe, family, order, class, phylum, kingdom, and domain. For the first mob type of just predator and prey for the domain. 

Metabolism is the rate at which a creature can convert fat into energy. Energy is what is uses to perform actions such as move or attack. There is active metabolism which is how fast the conversion is when the mob is performing an action and resting for when a mob is just sitting still as it is resting or when eating. 

Size is the factor for how much the fat value is. If a mob is a size of 1 then a fat value of 1 is the equilivant of one. If a mob is a size of 2 then 1 fat is more like 1.5 or 2. The more fat a mob with a larger size value has is then the more energy it takes to move or attack. A mob with a large size but low fat would be lean and able to move faster and take less energy to move. Will need to research and plan out if this method provides the necessary diveristy. 

Predators can attack and kill prey and even other predators. Prey type mobs specialise in defense and escaping. But Prey can attack but they are not generally specialized in it. 

What makes a mob more of a predator or prey is the food source. Prey tend to eat grass for its food source. While predators tend to consider prey its food source. 

Need to consider how to define the type physical attribute that determines the food source of grass or other mobs. Since there are carnivore, omnivore, and herbivore. Since the first types are just carnivore/predator and herbivore prey.

Need to better define how mobs attack. How is the amount of damage a mob can generate compare against the defence of a mob. Does a mob Size negate a portion of the attack or does the speed of the mob help negate the amount of damage? If a mob that is large with a slow speed have a high damage value but when attacking something smaller and faster would the smaller mob be able to evade and escape?

The behavior of the mobs and the the decision of what it wants to bred with is to further the population of the mobs species. 

There should be a mob life cycle just like animals. Baby - > juvenile -> adult -> Senior -> death. Will need a method to allow a creatures stats to age to the adult value and then decline. Will need to have some trade offs for how fast a create goes through the life stages. For example if the mob has herd tendencies will it naturally allow for a longer baby to juvenile period and for it to ultimately have a larger amount of stats during its adult period and live for a longer time which will allow to multiple breedings?

When breeding how many offspring will each breeding cycle produce. Will there be a gestation period for a preganant mob which allows for a more intact baby mob?

Are mobs male and female? Or can any mob breed with any other type of the same species mob. 

How do we determine what qualifies a mob to be one species versus another? How much of a varition will it take for a mob to be considered another species? Do we take a look at the adult physcial charestics then create a hash from the values or a statistical grouping of the values. And then if after so many succisive generations of mutations if the differing adult values fall outside of a range then is that considered a different species?

Based upong the Taxonomic rank we should track where each species comes from. This should be stored in a table so that a flow chart can be generated showing the lineage. When we determine that a new species is created there should be a method to create a new species name. For the initial method it should be something Latin sounding. In the future we should create pompt that can be sent to a llm based upon the stats of the adult to have the llm create a species that seems fitting based upon the genus it was derived from and what the stats represent. 

There should also be tracking for a mobs family tree. 

