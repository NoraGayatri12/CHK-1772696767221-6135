# train_priority_model.py
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
import pickle

# --- Sample training data ---
# Description examples of reports and their priorities
X = [
    "Urgent food and water needed immediately",
    "Need blankets for homeless people",
    "Lost child, immediate help required",
    "Request for school books",
    "Medical emergency, patient needs help",
    "Looking for volunteers for community clean-up",
    "Need support for vaccination camp",
    "Stranded elderly person needs help",
    "Help, child stuck in traffic accident",
    "Request for educational materials"
]

y = [
    "High",
    "Medium",
    "High",
    "Low",
    "High",
    "Low",
    "Medium",
    "High",
    "High",
    "Low"
]

# --- Train model ---
vectorizer = CountVectorizer()
X_vec = vectorizer.fit_transform(X)
model = MultinomialNB()
model.fit(X_vec, y)

# --- Save model ---
with open("priority_model.pkl", "wb") as f:
    pickle.dump((vectorizer, model), f)

print("Model trained and saved as 'priority_model.pkl'")