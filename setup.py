from setuptools import setup

with open('requirements.txt') as r:
    requirements = r.read().splitlines()

setup(
    name='TimetableBot',
    version='1.0',
    packages=[''],
    url='https://vk.link/bot_agz',
    license='',
    author='Nicare',
    author_email='my.profile.protect@gmail.com',
    description='Bot for AGZ MCHS',
    install_requires=requirements
)
